"""AlpaSim E2E challenge driver backed by Alpamayo 1.5 (int8, no-reasoning by default).

Structure follows NVIDIA's VAVAM sample driver (see NOTICE.md): the policy loads in a
background thread after the gRPC server starts; get_version reports UNAVAILABLE until a
warm-up inference has run; each Drive call runs inference inline when a new plan is due
(sim time, A15_INFERENCE_INTERVAL_US) and otherwise serves the cached plan; before the
first plan it returns a straight line at the current speed.

Inputs per plan: 4 frames per camera ending at the newest common frame time t0, chosen
nearest to t0 - k * A15_FRAME_DT_S (PAI sends 10 Hz, so 0.1 s spacing as in training;
nuPlan sends 2 Hz, so the nearest available frames are used and missing ones repeat the
oldest), and a 16-step, 0.1 s ego history ending at t0 in the t0 rig frame.
"""
from __future__ import annotations

import logging
import math
import os
import signal
import threading
import time
from collections import deque
from concurrent import futures
from dataclasses import dataclass, field
from io import BytesIO

_RUNTIME_WRITE_DIR_DEFAULTS = {
    "XDG_CACHE_HOME": "/tmp/.cache", "TORCH_HOME": "/tmp/torch", "HF_HOME": "/tmp/huggingface",
    "TRITON_CACHE_DIR": "/tmp/triton", "CUDA_CACHE_PATH": "/tmp/nv", "MPLCONFIGDIR": "/tmp/matplotlib",
    "ALPASIM_DRIVER_LOG_DIR": "/run/alpasim-driver",
}
for _k, _v in _RUNTIME_WRITE_DIR_DEFAULTS.items():
    os.environ.setdefault(_k, _v)
for _k in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_k, "2")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import numpy as np                                                  # noqa: E402
import torch                                                        # noqa: E402
from alpasim_grpc import API_VERSION_MESSAGE                        # noqa: E402
from alpasim_grpc.v0 import common_pb2, egodriver_pb2, egodriver_pb2_grpc  # noqa: E402
from PIL import Image                                               # noqa: E402

import grpc                                                         # noqa: E402

from .policy import CAMERA_NAME_TO_INDEX, NUPLAN_TO_SLOT, Alpamayo15Policy  # noqa: E402
from .route_choice import (RouteMemory, cap_speed_on_path, heading_change_deg, retime_path,  # noqa: E402
                           route_deviation, route_lateral_offset, route_parallel, route_path, route_pull,
                           time_warp_plan)
from .trajectory import CachedPlan, build_trajectory_from_plan, make_cached_plan  # noqa: E402
from .capture import Capturer, GroundTruthStore  # noqa: E402

LOGGER = logging.getLogger("a15_challenge_driver")
DEFAULT_PAI_CAMERAS = "camera_cross_left_120fov,camera_front_wide_120fov,camera_cross_right_120fov,camera_front_tele_30fov"
N_FRAMES, N_HIST, HIST_DT_S = 4, 16, 0.1


# ---------------------------------------------------------------- geometry helpers
def _quat_arr(q) -> np.ndarray:
    return np.array([q.w, q.x, q.y, q.z], dtype=np.float64)


def _quat_to_rot(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q / np.linalg.norm(q)
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
                     [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
                     [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)]])


def _interp_poses(ts: np.ndarray, pos: np.ndarray, quat: np.ndarray, t: np.ndarray):
    """Linear positions / normalised-lerp quaternions at times t. Outside the known range the
    trajectory is extended at the velocity of the nearest segment (orientation held)."""
    out_p = np.empty((len(t), 3)); out_q = np.empty((len(t), 4))
    for i, ti in enumerate(t):
        j = int(np.clip(np.searchsorted(ts, ti) - 1, 0, max(len(ts) - 2, 0)))
        if len(ts) == 1:
            out_p[i], out_q[i] = pos[0], quat[0]; continue
        dt = ts[j + 1] - ts[j]
        a = (ti - ts[j]) / dt if dt > 0 else 0.0
        out_p[i] = pos[j] + a * (pos[j + 1] - pos[j])
        q0, q1 = quat[j], quat[j + 1]
        if np.dot(q0, q1) < 0:
            q1 = -q1
        ac = min(max(a, 0.0), 1.0)
        q = (1 - ac) * q0 + ac * q1
        out_q[i] = q / np.linalg.norm(q)
    return out_p, out_q


def route_nav_text(xy: np.ndarray, turn_deg: float = 30.0, max_dist_m: float = 100.0,
                   dist_mode: str = "euclid") -> str | None:
    """'Turn left in 30m' style instruction (Alpamayo 1.5's navigation input) from the route waypoints
    in the rig frame (x forward, y left).

    The challenge runtime trims the first `route_start_offset_m` (40 m) of the route, so a turn that
    starts inside that window is already behind the first waypoint. Headings are therefore measured
    against the CAR's heading (rig x axis), not the route's first segment: the first route segment
    heading more than turn_deg off the car's heading marks the turn, and its distance is the Euclidean
    distance to that segment's start. None if the route runs straight ahead within max_dist_m.
    (v1 compared against the route's own first segment and fired in only 2/40 PAI sessions.)"""
    pts = xy[xy[:, 0] > -2.0] if len(xy) else xy
    if len(pts) < 2:
        return None
    seg = np.diff(pts, axis=0); L = np.linalg.norm(seg, axis=1)
    keep = L > 0.2
    if keep.sum() < 1:
        return None
    starts, seg = pts[:-1][keep], seg[keep]
    hd = np.arctan2(seg[:, 1], seg[:, 0])                  # relative to the car's heading
    for i in range(len(hd)):
        d = float(np.linalg.norm(starts[i]))
        if d > max_dist_m:
            return None
        if abs(hd[i]) > math.radians(turn_deg):
            if dist_mode == "intersect":
                # v3: the turn is where the turned road, extended back along this segment, meets the
                # car's forward axis (y = 0). v2 reported the distance to the first route waypoint,
                # which sits >= 40 m out even when the turn starts 15 m ahead.
                x1, y1 = starts[i]; dx, dy = seg[i]
                if abs(dy) > 1e-6:
                    xi = x1 - y1 * dx / dy
                    if 0.0 < xi <= x1:
                        d = xi
            return f"Turn {'left' if hd[i] > 0 else 'right'} in {int(round(d))}m"
    return None


def speed_scale_plan(xy: np.ndarray, yaw: np.ndarray, scale: float) -> tuple[np.ndarray, np.ndarray]:
    """Drive the same path `scale` times faster: point k of the new plan is point k*scale of the old one
    (linear interpolation), so the horizon shrinks to 6.4 s / scale. scale 1.0 returns the plan unchanged.
    PAI bench 2026-10-01: low progress cost 10.4 of 43.4 lost points; Alpamayo's path is good, its speed weak."""
    if scale == 1.0:
        return xy, yaw
    n = len(xy)
    src = np.arange(n) * scale
    src = src[src <= n - 1]
    i0 = np.floor(src).astype(int); i1 = np.minimum(i0 + 1, n - 1); a = (src - i0)[:, None]
    new_xy = xy[i0] * (1 - a) + xy[i1] * a
    dyaw = np.angle(np.exp(1j * (yaw[i1] - yaw[i0])))
    return new_xy, yaw[i0] + a[:, 0] * dyaw


def _yaw_of(q: np.ndarray) -> float:
    w, x, y, z = q
    return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))


# ---------------------------------------------------------------- policy handle
class _NoModel:
    """Stand-in policy for capture mode (A15_NO_MODEL=1): the ego follows the recording, the driver only records."""
    output_frequency_hz = 10.0


class PolicyHandle:
    """Loads the policy after gRPC startup; ready only after a warm-up inference."""

    def __init__(self, kwargs: dict) -> None:
        self._kwargs, self._lock = kwargs, threading.Lock()
        self._policy = None
        self._error: BaseException | None = None

    def start(self) -> None:
        if _GPU_THREAD is not None:          # load + warm-up on the same thread that will run every predict
            _GPU_THREAD.submit(self._load)
        else:
            threading.Thread(target=self._load, name="a15-loader", daemon=True).start()

    def get(self):
        with self._lock:
            return self._policy

    def error(self):
        with self._lock:
            return self._error

    def _load(self) -> None:
        if os.environ.get("A15_NO_MODEL", "0") == "1":              # capture mode: frames + recording only
            with self._lock:
                self._policy = _NoModel()
            LOGGER.info("policy ready after 0s (no model: capture mode)")
            return
        try:
            t0 = time.time()
            if os.environ.get("A15_FLASH", "0") == "1":             # FlashDrive policy (alpasim-jepa/pai_flashdrive)
                from .flash_policy import FlashAlpamayo15Policy
                kw = self._kwargs
                assert kw.get("force_start") and kw.get("num_samples", 1) == 1 and not kw.get("expert_ckpt"), \
                    "A15_FLASH=1 implements the forced-start, one-sample, released-expert path only"
                p = FlashAlpamayo15Policy(
                    **kw, paro_dir=os.environ["A15_PARO_DIR"],
                    compile_mode=os.environ.get("A15_FD_COMPILE", "max-autotune") or None,
                    steps=int(os.environ.get("A15_FD_STEPS", "8")),
                    cache_steps=tuple(int(x) for x in os.environ.get("A15_FD_CACHE_STEPS", "3,4,5,6").split(",") if x))
            else:
                p = Alpamayo15Policy(**self._kwargs)
            check_processor(p)
            # warm-up at a representative prompt size (4 cameras x 4 frames)
            h, w = target_hw(1080, 1920)
            fr = torch.randint(0, 255, (4, N_FRAMES, 3, h, w), dtype=torch.uint8)
            hx = torch.zeros(1, 1, N_HIST, 3); hr = torch.eye(3).expand(1, 1, N_HIST, 3, 3).clone()
            for _ in range(2):
                p.predict(fr, [0, 1, 2, 6], hx, hr)
            LOGGER.info("policy ready after %.0fs; peak reserved %.2f GiB", time.time() - t0,
                        torch.cuda.max_memory_reserved() / 2**30)
        except BaseException as exc:                           # noqa: BLE001
            LOGGER.exception("policy load failed")
            with self._lock:
                self._error = exc
            return
        with self._lock:
            self._policy = p


# All GPU work (model load, warm-up, every predict) runs on ONE dedicated thread. With predict called from
# whichever gRPC worker thread handled the Drive request, each new thread set up its own CUDA library state:
# on H100 the driver process grew in ~400 MiB steps from 14,578 to 17,340 MiB while torch's reserved memory
# stayed flat at 13.58 GiB (2026-10-07, job 13256940), above the 16 GiB per-driver contract.
# A15_ONE_GPU_THREAD=0 restores the old behaviour.
_ONE_GPU_THREAD = os.environ.get("A15_ONE_GPU_THREAD", "1") == "1"
_GPU_THREAD = futures.ThreadPoolExecutor(max_workers=1, thread_name_prefix="a15-gpu") if _ONE_GPU_THREAD else None


def on_gpu_thread(fn, *args, **kwargs):
    """Run fn on the dedicated GPU thread (or inline when disabled) and return its result."""
    if _GPU_THREAD is None:
        return fn(*args, **kwargs)
    return _GPU_THREAD.submit(fn, *args, **kwargs).result()


# Alpamayo 1.5 processor limits (alpamayo1_5.helper MIN_PIXELS / MAX_PIXELS) and the Qwen3-VL
# resize factor (patch 16 x merge 2); checked against the live processor at warm-up.
MIN_PIXELS, MAX_PIXELS, RESIZE_FACTOR = 163840, 196608, 32


def target_hw(h: int, w: int) -> tuple[int, int]:
    """Size the Qwen processor would resize an (h, w) image to. Frames are pre-resized to
    exactly this, so the processor does not resample again (and JPEG decode can use draft mode)."""
    from transformers.models.qwen2_vl.image_processing_qwen2_vl import smart_resize
    return tuple(smart_resize(h, w, factor=RESIZE_FACTOR, min_pixels=MIN_PIXELS, max_pixels=MAX_PIXELS))


def check_processor(policy) -> None:
    ip = policy._proc.image_processor
    got = (ip.patch_size * ip.merge_size, getattr(ip, "min_pixels", None) or ip.size.get("shortest_edge"),
           getattr(ip, "max_pixels", None) or ip.size.get("longest_edge"))
    assert got == (RESIZE_FACTOR, MIN_PIXELS, MAX_PIXELS), f"processor resize config changed: {got}"


# ---------------------------------------------------------------- session state
@dataclass
class SessionState:
    cams: list[str] = field(default_factory=list)           # logical ids, ascending Alpamayo slot
    slots: list[int] = field(default_factory=list)
    frames: dict[str, deque] = field(default_factory=dict)  # logical id -> deque[(t_us, CHW uint8 tensor)]
    poses: list[tuple[int, np.ndarray, np.ndarray]] = field(default_factory=list)  # (t_us, xyz, wxyz)
    speed: float = 0.0
    latest_pose: common_pb2.PoseAtTime | None = None
    cached_plan: CachedPlan | None = None
    route_xy: np.ndarray | None = None                      # latest route waypoints, rig frame
    sid: str = ""
    plan_nframes: int = 0                                   # distinct frames per camera behind the cached plan
    last_nav: str | None = None
    snapping: bool = False                                  # route snap active (hysteresis)
    route_mem: RouteMemory = field(default_factory=RouteMemory)   # recorded path seen so far, world frame
    gt: GroundTruthStore = field(default_factory=GroundTruthStore)   # recording (capture mode only)
    last_capture_us: int = -10**18
    stats: dict = field(default_factory=lambda: {"drive": 0, "infer": 0, "infer_err": 0, "fallback": 0,
                                                 "cached": 0, "rerouted": 0, "snapped": 0, "snapped_mem": 0,
                                                 "infer_s": 0.0})


class A15ChallengeDriver(egodriver_pb2_grpc.EgodriverServiceServicer):
    def __init__(self, *, handle: PolicyHandle, pai_cameras: list[str], interval_us: int, frame_dt_s: float,
                 nav: bool = False, log_choices: bool = False, early_replan: bool = False,
                 nav_dist: str = "euclid", speed_scale: float = 1.0, route_pull: float = 0.0,
                 route_pull_d0: float = 30.0, route_pull_d1: float = 45.0, speed_cams: bool = False,
                 route_snap: float = 0.0, route_snap_max_deg: float = 0.0, route_snap_min_offset: float = 0.0,
                 route_memory: bool = False, route_mem_debug: bool = False, route_mem_dev_min: float = 20.0,
                 snap_alat: float = 0.0, mem_geom_only: bool = False, capture_dir: str | None = None,
                 capture_every_us: int = 500_000, capture_max_dev_m: float = float("inf"),
                 capture_at_infer: bool = False,
                 time_scale: float = 1.0, ts_max_turn_deg: float = 10.0,
                 ts_skip_snapped: bool = True):
        self._handle, self._pai_cameras, self._nav = handle, pai_cameras, nav
        self._log_choices, self._early_replan, self._nav_dist = log_choices, early_replan, nav_dist
        self._speed_scale = speed_scale
        self._route_pull, self._route_pull_d0, self._route_pull_d1 = route_pull, route_pull_d0, route_pull_d1
        self._speed_cams = speed_cams
        self._route_snap, self._route_snap_max_deg = route_snap, route_snap_max_deg
        self._route_snap_min_offset = route_snap_min_offset
        self._route_memory = route_memory
        self._route_mem_debug, self._route_mem_dev_min = route_mem_debug, route_mem_dev_min
        self._snap_alat, self._mem_geom_only = snap_alat, mem_geom_only
        self._capturer = Capturer(capture_dir, capture_every_us) if capture_dir else None
        self._capture_max_dev = float(capture_max_dev_m)
        self._capture_at_infer = bool(capture_at_infer)
        self._time_scale, self._ts_max_turn_deg, self._ts_skip_snapped = time_scale, ts_max_turn_deg, ts_skip_snapped
        self._interval_us, self._frame_dt_us = interval_us, int(frame_dt_s * 1e6)
        self._sessions: dict[str, SessionState] = {}
        self._lock = threading.RLock()
        self._infer_lock = threading.Lock()                  # one model, one GPU: serialise inference
        self._target_hw: dict[tuple[int, int], tuple[int, int]] = {}
        self._server: grpc.Server | None = None

    def attach_server(self, server) -> None:
        self._server = server

    # ------------------------------------------------------------ sessions
    def start_session(self, request, context):
        avail = [c.logical_id for c in request.rollout_spec.vehicle.available_cameras if c.logical_id]
        pai = [c for c in self._pai_cameras if c in avail]
        if pai:
            chosen = sorted(((CAMERA_NAME_TO_INDEX[c], c) for c in pai))
        else:
            chosen = sorted(((NUPLAN_TO_SLOT[c], c) for c in avail if c in NUPLAN_TO_SLOT))
        s = SessionState(cams=[c for _, c in chosen], slots=[k for k, _ in chosen], sid=request.session_uuid)
        s.frames = {c: deque(maxlen=24) for c in s.cams}
        with self._lock:
            self._sessions[request.session_uuid] = s
        LOGGER.info("session %s: cameras %s (slots %s) of %d available", request.session_uuid, s.cams, s.slots, len(avail))
        return common_pb2.SessionRequestStatus()

    def close_session(self, request, context):
        with self._lock:
            s = self._sessions.pop(request.session_uuid, None)
        if s is not None:
            st = s.stats
            if torch.cuda.is_available():
                free, total = torch.cuda.mem_get_info()
                LOGGER.info("memory at close %s: torch reserved %.2f GiB (peak %.2f), allocated %.2f GiB (peak %.2f), "
                            "device used %.2f GiB of %.2f, threads %d", request.session_uuid[:8],
                            torch.cuda.memory_reserved() / 2**30, torch.cuda.max_memory_reserved() / 2**30,
                            torch.cuda.memory_allocated() / 2**30, torch.cuda.max_memory_allocated() / 2**30,
                            (total - free) / 2**30, total / 2**30, threading.active_count())
            LOGGER.info("closed session %s: drive %d, inferences %d (errors %d, mean %.3fs), cached %d, fallback %d, "
                        "rerouted %d, snapped %d (memory %d), last nav %r", request.session_uuid, st["drive"], st["infer"],
                        st["infer_err"], st["infer_s"] / max(st["infer"], 1), st["cached"], st["fallback"], st["rerouted"],
                        st["snapped"], st["snapped_mem"], s.last_nav)
        return common_pb2.Empty()

    # ------------------------------------------------------------ observations
    def submit_image_observation(self, request, context):
        img = request.camera_image
        s = self._get_session(request.session_uuid, context)
        if img.logical_id not in s.frames:
            return common_pb2.Empty()
        im = Image.open(BytesIO(img.image_bytes))
        key = (im.height, im.width)
        if key not in self._target_hw:
            self._target_hw[key] = target_hw(*key)
        th, tw = self._target_hw[key]
        im.draft("RGB", (tw, th))                            # JPEG decodes at a reduced scale >= target
        im = im.convert("RGB").resize((tw, th), Image.BICUBIC)
        t = torch.from_numpy(np.asarray(im).copy()).permute(2, 0, 1)
        with self._lock:
            s.frames[img.logical_id].append((int(img.frame_end_us), t))
        return common_pb2.Empty()

    def submit_egomotion_observation(self, request, context):
        s = self._get_session(request.session_uuid, context)
        with self._lock:
            for p in request.trajectory.poses:
                s.poses.append((int(p.timestamp_us), np.array([p.pose.vec.x, p.pose.vec.y, p.pose.vec.z]),
                                _quat_arr(p.pose.quat)))
                s.latest_pose = p
            s.poses.sort(key=lambda x: x[0])
            s.poses = s.poses[-200:]
            if request.dynamic_states:
                v = request.dynamic_states[-1].linear_velocity
                s.speed = float(math.hypot(v.x, v.y))
            elif len(s.poses) >= 2:
                (ta, pa, _), (tb, pb, _) = s.poses[-2], s.poses[-1]
                if tb > ta:
                    s.speed = float(np.linalg.norm((pb - pa)[:2]) / ((tb - ta) / 1e6))
        return common_pb2.Empty()

    def submit_route(self, request, context):
        s = self._get_session(request.session_uuid, context)
        wps = np.array([[w.x, w.y] for w in request.route.waypoints], dtype=np.float64).reshape(-1, 2)
        with self._lock:
            first = s.route_xy is None
            s.route_xy = wps
            if self._route_memory and len(s.poses) >= 1 and len(wps):
                ts = np.array([p[0] for p in s.poses], dtype=np.float64)
                tr = float(request.route.timestamp_us) or ts[-1]
                hp, hq = _interp_poses(ts, np.stack([p[1] for p in s.poses]), np.stack([p[2] for p in s.poses]),
                                       np.array([tr]))
                s.route_mem.add(wps, hp[0], _quat_to_rot(hq[0]))
                if self._route_mem_debug:
                    LOGGER.info("routemem %s route_ts %d poses [%d .. %d] n %d, pose %s yaw %.3f, first wp rig %s, "
                                "merge dist %s, mem %d", s.sid[:8], int(request.route.timestamp_us), int(ts[0]),
                                int(ts[-1]), len(ts), np.round(hp[0][:2], 2).tolist(), _yaw_of(hq[0]),
                                np.round(wps[0], 2).tolist(), None if s.route_mem.last_merge is None
                                else round(s.route_mem.last_merge, 2), len(s.route_mem.pts))
        if first and self._nav:
            LOGGER.info("session %s first route: %d waypoints, first %s last %s -> nav %r", request.session_uuid,
                        len(wps), np.round(wps[0], 1).tolist() if len(wps) else None,
                        np.round(wps[-1], 1).tolist() if len(wps) else None, route_nav_text(wps, dist_mode=self._nav_dist))
        return common_pb2.Empty()

    def submit_recording_ground_truth(self, request, context):
        # local data generation only (capture mode); the official evaluator does not send the recording
        if self._capturer is None:
            return common_pb2.Empty()
        s = self._get_session(request.session_uuid, context)
        gt = request.ground_truth
        ps = gt.trajectory.poses
        if not ps:
            return common_pb2.Empty()
        times = np.array([p.timestamp_us for p in ps], dtype=np.float64)
        xyz = np.array([[p.pose.vec.x, p.pose.vec.y, p.pose.vec.z] for p in ps], dtype=np.float64)
        R = np.stack([_quat_to_rot(_quat_arr(p.pose.quat)) for p in ps])
        with self._lock:
            if len(s.poses) < 1:
                return common_pb2.Empty()
            ts = np.array([p[0] for p in s.poses], dtype=np.float64)
            hp, hq = _interp_poses(ts, np.stack([p[1] for p in s.poses]), np.stack([p[2] for p in s.poses]),
                                   np.array([float(gt.timestamp_us)]))
            s.gt.set_from_rig(times, xyz, R, hp[0], _quat_to_rot(hq[0]))
        return common_pb2.Empty()

    def _capture_inference(self, s: SessionState, frames, hx, hr, t0, anchor, samples) -> None:
        """RoaD-style capture (A15_CAPTURE_AT_INFER=1, A15_CHOOSER=record): the exact frames and history the
        policy just planned from, the recorded future from the ego's pose, and all K policy samples; the trainer
        picks the sample nearest the recording as the target (recovery label when none is within 3 m)."""
        ap, aq = anchor.pose.vec, anchor.pose.quat
        p0, R0 = np.array([ap.x, ap.y, ap.z]), _quat_to_rot(np.array([aq.w, aq.x, aq.y, aq.z]))
        with self._lock:
            if self._capture_max_dev < float("inf"):
                off = s.gt.offset_at(t0, p0, R0)
                if off is None or float(np.hypot(off[0], off[1])) > self._capture_max_dev:
                    return
            fut = s.gt.future_in_frame(t0, p0, R0)
            slots = list(s.slots)
        if fut is None:
            return
        self._capturer.save(s.sid, t0, frames, slots, hx, hr, *fut,
                            samp_xyz=samples[0].astype(np.float32), samp_rot=samples[1].astype(np.float32))

    def _maybe_capture(self, s: SessionState, now: int) -> None:
        with self._lock:
            if now - s.last_capture_us < self._capturer.every_us:
                return
            batch = self._gather(s)
            if batch is None:
                return
            frames, hx, hr, t0, anchor = batch
            ap, aq = anchor.pose.vec, anchor.pose.quat
            p0, R0 = np.array([ap.x, ap.y, ap.z]), _quat_to_rot(np.array([aq.w, aq.x, aq.y, aq.z]))
            if self._capture_max_dev < float("inf"):                 # policy-driven capture: drivable recoveries only
                off = s.gt.offset_at(t0, p0, R0)
                if off is None or float(np.hypot(off[0], off[1])) > self._capture_max_dev:
                    return
            fut = s.gt.future_in_frame(t0, p0, R0)
            if fut is None:
                return
            s.last_capture_us = now
            slots = list(s.slots)
        self._capturer.save(s.sid, t0, frames, slots, hx, hr, *fut)

    # ------------------------------------------------------------ drive
    def drive(self, request, context):
        s = self._get_session(request.session_uuid, context)
        now = int(request.time_now_us)
        with self._lock:
            s.stats["drive"] += 1
        if self._capturer is not None and not self._capture_at_infer:
            self._maybe_capture(s, now)
        self._maybe_infer(s, now)
        with self._lock:
            plan, pose, speed = s.cached_plan, s.latest_pose, s.speed
            s.stats["cached" if plan is not None else "fallback"] += 1
        traj = build_trajectory_from_plan(plan, pose, now, callback_frequency_hz=10.0,
                                          fallback_speed_mps=max(1.0, speed), max_horizon_s=6.0)
        return egodriver_pb2.DriveResponse(trajectory=traj)

    def _maybe_infer(self, s: SessionState, now: int) -> None:
        policy = self._handle.get()
        if policy is None or isinstance(policy, _NoModel):
            return
        with self._lock:
            plan = s.cached_plan
            nfr = min((len(s.frames[c]) for c in s.cams), default=0)
            # early replan: while the plan was made from fewer than N_FRAMES distinct frames (session
            # start; on nuPlan the first plan sees ONE frame), replan as soon as a new frame arrives
            early = self._early_replan and s.plan_nframes < N_FRAMES and nfr > s.plan_nframes
            if plan is not None and now - plan.created_time_us < self._interval_us and not early:
                return
            batch = self._gather(s)
            if self._log_choices:
                LOGGER.info("plan %s now %d: frames/cam %s, plan_nframes %d, early %s, since last %s",
                            s.sid[:8], now, {c: len(s.frames[c]) for c in s.cams}, s.plan_nframes, early,
                            None if plan is None else now - plan.created_time_us)
        if batch is None:
            return
        frames, hx, hr, t0, anchor = batch
        if self._log_choices and s.stats["infer"] == 0:
            with self._lock:
                LOGGER.info("first plan %s: now %d t0 %d, poses %d spanning %.2fs, frames/cam %s, hist x %s",
                            s.sid, now, t0, len(s.poses), (s.poses[-1][0] - s.poses[0][0]) / 1e6,
                            {c: [round((f[0] - t0) / 1e6, 2) for f in s.frames[c]] for c in s.cams[:1]},
                            np.round(hx[0, 0, ::5, 0].numpy(), 1).tolist())
        with self._lock:
            route = s.route_xy
        nav = None
        if self._nav:
            nav = route_nav_text(route, dist_mode=self._nav_dist) if route is not None else None
            s.last_nav = nav
        t = time.time()
        try:
            with self._infer_lock:
                if self._speed_cams and len(s.slots) > 4:
                    # hybrid: route (path) from the usual 4 cameras with the chooser; speed from a 1-sample
                    # plan that also sees the rear cameras (PAI 2026-10-08: rear cameras cut rear-end hits)
                    i4 = [i for i, sl in enumerate(s.slots) if sl in (0, 1, 2, 6)]
                    xy, yaw, info = on_gpu_thread(policy.predict, frames[i4], [s.slots[i] for i in i4], hx, hr,
                                                  nav_text=nav, route_xy=route)
                    xs, _, _ = on_gpu_thread(policy.predict, frames, s.slots, hx, hr, route_xy=None, num_samples=1)
                    xy, yaw = retime_path(np.asarray(xy), np.asarray(xs))
                else:
                    xy, yaw, info = on_gpu_thread(policy.predict, frames, s.slots, hx, hr, nav_text=nav, route_xy=route)
        except Exception:                                    # noqa: BLE001
            LOGGER.exception("inference failed")
            with self._lock:
                s.stats["infer_err"] += 1
            return
        samples = getattr(policy, "last_samples", None)
        if self._capturer is not None and self._capture_at_infer and samples is not None:
            self._capture_inference(s, frames, hx, hr, t0, anchor, samples)
        xy, yaw = speed_scale_plan(np.asarray(xy), np.asarray(yaw), self._speed_scale)
        if self._route_pull > 0:
            xy, yaw = route_pull(xy, yaw, route, self._route_pull, self._route_pull_d0, self._route_pull_d1)
        snapped = False
        if self._route_snap > 0:
            # drive onto the route when the plan leaves it by more than route_snap metres (half that while a
            # snap is under way, so a lane change is not abandoned halfway); the model's plan keeps the speed
            # route memory: the whole recorded path from the car onwards (earlier routes fill the ~40 m before
            # the current route's first waypoint), so turns can be followed without cutting corners
            mpath = None
            if self._route_memory:
                ap, aq = anchor.pose.vec, anchor.pose.quat
                with self._lock:
                    mpath = s.route_mem.path_in_frame(np.array([ap.x, ap.y, ap.z]),
                                                      _quat_to_rot(np.array([aq.w, aq.x, aq.y, aq.z])),
                                                      join_m=float(np.clip(2.5 * s.speed, 15.0, 60.0)))
            # with memory, deviation counts only path points >= route_mem_dev_min ahead (default 20 m): the near
            # points made a 1.5-2 m offset within the lane trigger snaps, and the car weaved between the model's
            # line and the recorded one (PAI 2026-10-19, fb501e/31f39b); the route alone starts ~40 m ahead
            dev = route_deviation(xy, mpath[np.linalg.norm(mpath, axis=1) >= self._route_mem_dev_min]
                                  if mpath is not None and not self._mem_geom_only else route)
            limit = self._route_snap / 2 if s.snapping else self._route_snap
            # route_snap_max_deg > 0: only where the route runs nearly parallel (lane change, exit), not on
            # turns, where the curve to a waypoint ~40 m ahead cuts the corner (PAI 2026-10-10)
            # A15_ROUTE_MEM_GEOM_ONLY=1: snap decisions exactly as without memory (route deviation + angle guard);
            # memory only supplies the path's geometry (the recorded lane change instead of the Hermite bridge)
            ok = (mpath is not None and not self._mem_geom_only) or self._route_snap_max_deg <= 0 \
                or route_parallel(route, self._route_snap_max_deg)
            # route_snap_min_offset > 0: only when the route itself leaves our lane (its first waypoint is that far
            # to the side), so a model swerve around something on a route that stays in lane is not overridden
            # (PAI 2026-10-11: fb501e, route at y~0, model swerved ~3 m, snap -> corridor exit). A snap under
            # way continues regardless, so a lane change is finished.
            if ok and self._route_snap_min_offset > 0 and not s.snapping:
                ok = route_lateral_offset(route) >= self._route_snap_min_offset
            path = (mpath if mpath is not None else route_path(route)) if ok and dev is not None and dev > limit else None
            if path is not None:
                # memory paths can carry the recorded turn: cap the model's speed by the path's curvature
                # (A15_SNAP_ALAT m/s^2 lateral, 0 = off)
                prog = (cap_speed_on_path(path, np.asarray(xy), a_lat=self._snap_alat)
                        if mpath is not None and self._snap_alat > 0 else np.asarray(xy))
                xy, yaw = retime_path(path, prog)
                snapped = True
                if mpath is not None:
                    with self._lock:
                        s.stats["snapped_mem"] += 1
                    if self._log_choices:
                        LOGGER.info("memsnap %s t0 %d: dev %.1f, memory path %s", s.sid, t0, dev,
                                    np.round(mpath[::max(1, len(mpath) // 8)][:8], 1).tolist())
            s.snapping = snapped
        # the organisers' time warp (A15_TIME_SCALE; their GTRS sample, via alpasim-jepa) on near-straight plans
        # only (A15_TS_MAX_TURN_DEG over 4 s), and not on snapped plans (A15_TS_SKIP_SNAPPED, cf. their judge)
        if self._time_scale > 1.0 and not (self._ts_skip_snapped and snapped) \
                and heading_change_deg(np.asarray(xy)) < self._ts_max_turn_deg:
            xy, yaw = time_warp_plan(np.asarray(xy), np.asarray(yaw), self._time_scale)
        new = make_cached_plan(created_time_us=t0, anchor_pose=anchor, trajectory_xy=xy, headings=yaw,
                               source_frequency_hz=policy.output_frequency_hz)
        with self._lock:
            s.stats["infer"] += 1; s.stats["infer_s"] += time.time() - t
            s.stats["rerouted"] += int(info.get("choice", 0) != 0)
            s.stats["snapped"] += int(snapped)
            if new is not None:
                s.cached_plan, s.plan_nframes = new, nfr
        if self._log_choices and info.get("costs") is not None:
            LOGGER.info("choice %s t0 %d: costs %s ends %s -> %d route %s", s.sid, t0, info["costs"], info["ends"],
                        info["choice"], None if route is None else np.round(route, 1).tolist())

    def _gather(self, s: SessionState):
        """Frames (n_cam, 4, 3, H, W), ego history, t0 and the anchor pose; None if not ready."""
        if not s.cams or any(len(s.frames[c]) == 0 for c in s.cams) or len(s.poses) < 2:
            return None
        t0 = min(s.frames[c][-1][0] for c in s.cams)
        per_cam = []
        for c in s.cams:
            buf = [f for f in s.frames[c] if f[0] <= t0]
            if not buf:
                return None
            picked, used = [], set()
            for k in range(N_FRAMES - 1, -1, -1):
                target = t0 - k * self._frame_dt_us
                cand = [(abs(ts - target), i) for i, (ts, _) in enumerate(buf) if i not in used]
                i = min(cand)[1] if cand else 0
                used.add(i); picked.append(buf[i])
            picked.sort(key=lambda f: f[0])
            shapes = {f[1].shape for f in picked}
            if len(shapes) != 1:
                return None
            per_cam.append(torch.stack([f[1] for f in picked]))
        if len({p.shape for p in per_cam}) != 1:
            return None                                      # cameras of different sizes: wait
        frames = torch.stack(per_cam)
        ts = np.array([p[0] for p in s.poses], dtype=np.float64)
        pos = np.stack([p[1] for p in s.poses]); quat = np.stack([p[2] for p in s.poses])
        th = t0 - np.arange(N_HIST - 1, -1, -1) * HIST_DT_S * 1e6
        hp, hq = _interp_poses(ts, pos, quat, th)
        R0 = _quat_to_rot(hq[-1])
        hx = (hp - hp[-1]) @ R0                                 # rows: R0^T (p - p0)
        hr = np.stack([R0.T @ _quat_to_rot(q) for q in hq])
        anchor = common_pb2.PoseAtTime(
            timestamp_us=int(t0),
            pose=common_pb2.Pose(vec=common_pb2.Vec3(x=float(hp[-1][0]), y=float(hp[-1][1]), z=float(hp[-1][2])),
                                 quat=common_pb2.Quat(w=float(hq[-1][0]), x=float(hq[-1][1]),
                                                      y=float(hq[-1][2]), z=float(hq[-1][3]))))
        return (frames, torch.from_numpy(hx).float()[None, None], torch.from_numpy(hr).float()[None, None],
                int(t0), anchor)

    # ------------------------------------------------------------ misc
    def get_version(self, request, context):
        err = self._handle.error()
        if err is not None:
            context.abort(grpc.StatusCode.UNAVAILABLE, f"policy load failed: {err}")
        if self._handle.get() is None:
            context.abort(grpc.StatusCode.UNAVAILABLE, "policy is still loading")
        return common_pb2.VersionId(version_id="a15-int8-e2e-driver", git_hash=os.environ.get("A15_GIT_HASH", "local"),
                                    grpc_api_version=API_VERSION_MESSAGE)

    def shut_down(self, request, context):
        if self._server is not None:
            threading.Thread(target=lambda: (time.sleep(0.05), self._server.stop(grace=0.0)), daemon=True).start()
        return common_pb2.Empty()

    def _get_session(self, uuid: str, context) -> SessionState:
        with self._lock:
            s = self._sessions.get(uuid)
        if s is None:
            context.abort(grpc.StatusCode.NOT_FOUND, f"unknown session {uuid}")
        return s


def main() -> None:
    for k in _RUNTIME_WRITE_DIR_DEFAULTS:
        try:
            os.makedirs(os.environ[k], exist_ok=True)
        except OSError:
            if k == "ALPASIM_DRIVER_LOG_DIR":
                os.environ[k] = "/tmp/alpasim-driver"; os.makedirs(os.environ[k], exist_ok=True)
            else:
                raise
    torch.set_num_threads(int(os.environ.get("TORCH_NUM_THREADS", "2")))
    logging.basicConfig(level=os.environ.get("ALPASIM_DRIVER_LOG_LEVEL", "INFO"),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    assets = os.environ.get("A15_ASSETS", "/app/assets")
    handle = PolicyHandle(dict(
        model_dir=os.environ.get("A15_MODEL_DIR", f"{assets}/alpamayo15"),
        vlm_dir=os.environ.get("A15_VLM_DIR", f"{assets}/qwen3vl8b"),
        processor_dir=os.environ.get("A15_PROCESSOR_DIR", f"{assets}/qwen3vl2b"),
        quant=os.environ.get("A15_QUANT", "int8wo"),
        reasoning=os.environ.get("A15_REASONING", "0") == "1",
        embed_cpu=os.environ.get("A15_EMBED_CPU", "1") == "1",
        cuda_graph=os.environ.get("A15_CUDA_GRAPH", "0") == "1",
        num_samples=int(os.environ.get("A15_NUM_SAMPLES", "1")),
        chooser=os.environ.get("A15_CHOOSER", "medoid"),
        route_margin=float(os.environ.get("A15_ROUTE_MARGIN", "2.0")),
        route_min_len=float(os.environ.get("A15_ROUTE_MIN_LEN", "0")),
        route_big_gap=float(os.environ.get("A15_ROUTE_BIG_GAP", "0")),
        route_big_gap_min_len=float(os.environ.get("A15_ROUTE_BIG_GAP_MIN_LEN", "0")),
        diffusion_temperature=float(os.environ.get("A15_DIFF_TEMP", "1.0")),
        fast_tol=float(os.environ.get("A15_FAST_TOL", "1.0")),
        expert_ckpt=os.environ.get("A15_EXPERT_CKPT") or None,
        stall_m=float(os.environ.get("A15_STALL_M", "3.0")),
        force_start=os.environ.get("A15_FORCE_TRAJ_START", "0") == "1"))
    service = A15ChallengeDriver(
        handle=handle,
        # "," or ";" separated (sbatch --export splits values on commas)
        pai_cameras=[c.strip() for c in os.environ.get("A15_PAI_CAMERAS", DEFAULT_PAI_CAMERAS).replace(";", ",").split(",")
                     if c.strip()],
        interval_us=int(os.environ.get("A15_INFERENCE_INTERVAL_US", "500000")),
        frame_dt_s=float(os.environ.get("A15_FRAME_DT_S", "0.1")),
        nav=os.environ.get("A15_NAV", "0") == "1",
        log_choices=os.environ.get("A15_LOG_CHOICES", "0") == "1",
        early_replan=os.environ.get("A15_EARLY_REPLAN", "0") == "1",
        nav_dist=os.environ.get("A15_NAV_DIST", "euclid"),
        speed_scale=float(os.environ.get("A15_SPEED_SCALE", "1.0")),
        route_pull=float(os.environ.get("A15_ROUTE_PULL", "0")),
        route_pull_d0=float(os.environ.get("A15_ROUTE_PULL_D0", "30")),
        route_pull_d1=float(os.environ.get("A15_ROUTE_PULL_D1", "45")),
        speed_cams=os.environ.get("A15_SPEED_CAMS", "4") == "6",
        route_snap=float(os.environ.get("A15_ROUTE_SNAP", "0")),
        route_snap_max_deg=float(os.environ.get("A15_ROUTE_SNAP_MAX_DEG", "0")),
        route_snap_min_offset=float(os.environ.get("A15_ROUTE_SNAP_MIN_OFFSET", "0")),
        route_memory=os.environ.get("A15_ROUTE_MEMORY", "0") == "1",
        route_mem_debug=os.environ.get("A15_ROUTE_MEM_DEBUG", "0") == "1",
        route_mem_dev_min=float(os.environ.get("A15_ROUTE_MEM_DEV_MIN", "20")),
        snap_alat=float(os.environ.get("A15_SNAP_ALAT", "0")),
        mem_geom_only=os.environ.get("A15_ROUTE_MEM_GEOM_ONLY", "0") == "1",
        capture_dir=os.environ.get("A15_CAPTURE_DIR") or None,
        capture_every_us=int(os.environ.get("A15_CAPTURE_EVERY_US", "500000")),
        capture_max_dev_m=float(os.environ.get("A15_CAPTURE_MAX_DEV_M", "inf")),
        capture_at_infer=os.environ.get("A15_CAPTURE_AT_INFER", "0") == "1",
        time_scale=float(os.environ.get("A15_TIME_SCALE", "1.0")),
        ts_max_turn_deg=float(os.environ.get("A15_TS_MAX_TURN_DEG", "10")),
        ts_skip_snapped=os.environ.get("A15_TS_SKIP_SNAPPED", "1") == "1")
    host, port = os.environ.get("ALPASIM_DRIVER_HOST", "0.0.0.0"), int(os.environ.get("ALPASIM_DRIVER_PORT", "6789"))
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=int(os.environ.get("ALPASIM_DRIVER_GRPC_WORKERS", "8"))))
    egodriver_pb2_grpc.add_EgodriverServiceServicer_to_server(service, server)
    service.attach_server(server)
    if server.add_insecure_port(f"{host}:{port}") == 0:
        raise RuntimeError(f"failed to bind {host}:{port}")
    signal.signal(signal.SIGTERM, lambda *_: server.stop(grace=0.0))
    signal.signal(signal.SIGINT, lambda *_: server.stop(grace=0.0))
    server.start()
    LOGGER.info("Alpamayo 1.5 driver listening on %s:%d (replica %s/%s)", host, port,
                os.environ.get("ALPASIM_CONTESTANT_REPLICA_INDEX", "?"), os.environ.get("ALPASIM_CONTESTANT_REPLICAS", "?"))
    handle.start()
    server.wait_for_termination()


if __name__ == "__main__":
    main()
