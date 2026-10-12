"""py123d_garage AlpaSim driver with our add-ons, without modifying its code.

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0, v0.1.1) after wrapping
`driver_service._make_plan`, the one function that receives each fresh rig-frame plan ([8, 2] at 0.5 s):
  GARAGE_TIME_SCALE in [1.0, 1.25]: the organisers' trajectory time warp (wajepa_challenge/timewarp.py,
  same rule as their GTRS sample), applied to the plan before it is anchored and cached.
  GARAGE_TS_MAX_TURN_DEG (default off): apply the warp only if the plan's heading change over its
  4 s is below this many degrees (straight roads); curves keep the original timing. At scale 1.10 the
  warp helped 72 scenes and hurt 16, the losses mostly offroad in curves (LEDGER 2026-10-03).
  GARAGE_JUDGE=gtrs: the GTRS-Dense judge from the WA-JEPA driver (wajepa_challenge/judge.py) on py123d's
  plan, before the warp. GARAGE_JUDGE_RADIUS / GARAGE_JUDGE_MARGIN as WAJEPA_JUDGE_* (defaults 1 m and 1,
  the best WA-JEPA setting). GARAGE_JUDGE_STALL_M > 0 adds the judge's stall rescue (judge.py). It reads the raw 1920x1080 CAM_L0/F0/R0 frames at py123d's anchor time and
  ego velocity/acceleration and a drive command (GARAGE_JUDGE_COMMAND organisers|bridge) for GTRS's
  status input; py123d itself does not use any of these, so they are kept here per session.
  GARAGE_TS_SKIP_JUDGED=1: no time warp when the judge substituted a GTRS path (judge + warp together
  added collisions, LEDGER 2026-10-04).
"""
from __future__ import annotations

import importlib.util
import json
import logging
import math
import os
import pathlib
import threading
from collections import OrderedDict

import numpy as np

_TW = pathlib.Path(__file__).resolve().parent.parent / "wajepa_challenge" / "timewarp.py"
_spec = importlib.util.spec_from_file_location("_timewarp", _TW)      # no WA-JEPA package import
timewarp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(timewarp)

from py123d_garage.evaluation.alpasim import evaluate                    # noqa: E402
from py123d_garage.evaluation.alpasim.help import driver_service        # noqa: E402

LOG = logging.getLogger("garage_addons")
TIME_SCALE = float(os.environ.get("GARAGE_TIME_SCALE", "1.0"))
MAX_TURN_DEG = float(os.environ.get("GARAGE_TS_MAX_TURN_DEG", "inf"))
JUDGE = os.environ.get("GARAGE_JUDGE", "")
JUDGE_COMMAND = os.environ.get("GARAGE_JUDGE_COMMAND", "organisers")
if JUDGE not in ("", "gtrs"):
    raise ValueError(f"GARAGE_JUDGE must be empty or gtrs, got {JUDGE!r}")
if JUDGE_COMMAND not in ("organisers", "bridge"):
    raise ValueError(f"GARAGE_JUDGE_COMMAND must be organisers or bridge, got {JUDGE_COMMAND!r}")
JUDGE_CAMERAS = ("CAM_L0", "CAM_F0", "CAM_R0")
TS_SKIP_JUDGED = os.environ.get("GARAGE_TS_SKIP_JUDGED", "0") == "1"
_judged = threading.local()     # drive() calls _plan then _make_plan on the same thread


def _heading_change_deg(xy: np.ndarray) -> float:
    d = np.diff(np.vstack([np.zeros(2), xy]), axis=0)
    moving = np.linalg.norm(d, axis=1) > 0.2
    if moving.sum() < 2:
        return 0.0
    h = np.unwrap(np.arctan2(d[moving, 1], d[moving, 0]))
    return float(np.degrees(np.abs(h - h[0]).max()))

_make_plan = driver_service._make_plan


def _make_plan_with_addons(positions_rig, ego_pose_local, time_now_us, interval_us):
    xy = np.asarray(positions_rig, np.float64)
    substituted, _judged.substituted = getattr(_judged, "substituted", False), False
    if (TIME_SCALE != 1.0 and not (TS_SKIP_JUDGED and substituted) and interval_us == 500_000 and xy.shape[0] == 8
            and _heading_change_deg(xy) < MAX_TURN_DEG):
        plan = np.column_stack([xy, np.zeros(len(xy))])
        xy = timewarp.warp_plan(plan, TIME_SCALE)[:, :2]
    return _make_plan(xy, ego_pose_local, time_now_us, interval_us)


driver_service._make_plan = _make_plan_with_addons


# ---- GTRS judge (GARAGE_JUDGE=gtrs)
class _JudgeInputs:
    def __init__(self) -> None:
        self.frames = {c: OrderedDict() for c in JUDGE_CAMERAS}    # frame_end_us -> RGB uint8 [1080, 1920, 3]
        self.velocity = np.zeros(2, np.float32)
        self.acceleration = np.zeros(2, np.float32)
        self.command = None


_inputs: dict[str, _JudgeInputs] = {}
_inputs_lock = threading.Lock()
_judge_lock = threading.Lock()
_judge = None


def _session_inputs(session_uuid: str) -> _JudgeInputs:
    with _inputs_lock:
        return _inputs.setdefault(session_uuid, _JudgeInputs())


def _plan_with_yaw(xy: np.ndarray) -> np.ndarray:
    """[8, 2] -> [8, 3]: yaw from the step direction, held through (near-)stationary steps."""
    d = np.diff(np.vstack([np.zeros(2), xy]), axis=0)
    yaw, last = np.zeros(len(xy)), 0.0
    for i, (dx, dy) in enumerate(d):
        if math.hypot(dx, dy) > 0.05:
            last = math.atan2(dy, dx)
        yaw[i] = last
    return np.column_stack([xy, np.unwrap(yaw)])


def _wrap(name):
    def deco(fn):
        original = getattr(driver_service.GarageDriver, name)
        setattr(driver_service.GarageDriver, name, lambda self, *a: fn(original, self, *a))
        return fn
    return deco


def _install_judge() -> None:
    from wajepa_challenge.navigation import DriveCommand, command_from_route, command_one_hot
    from wajepa_challenge.route_bridge import bridge_one_hot
    unknown = command_one_hot(DriveCommand.UNKNOWN)

    @_wrap("submit_image_observation")
    def _image(original, self, request, context):
        out = original(self, request, context)
        logical_id = request.camera_image.logical_id
        if logical_id in JUDGE_CAMERAS:
            image = driver_service._decode_image(request.camera_image.image_bytes)
            if image.shape == (1080, 1920, 3):
                frames = _session_inputs(request.session_uuid).frames[logical_id]
                with _inputs_lock:
                    frames[int(request.camera_image.frame_end_us)] = image
                    while len(frames) > 2:
                        frames.popitem(last=False)
        return out

    @_wrap("submit_egomotion_observation")
    def _egomotion(original, self, request, context):
        out = original(self, request, context)
        if request.trajectory.poses and len(request.dynamic_states) == len(request.trajectory.poses):
            state = request.dynamic_states[-1]
            inputs = _session_inputs(request.session_uuid)
            with _inputs_lock:
                inputs.velocity = np.array([state.linear_velocity.x, state.linear_velocity.y], np.float32)
                inputs.acceleration = np.array([state.linear_acceleration.x, state.linear_acceleration.y], np.float32)
        return out

    @_wrap("submit_route")
    def _route(original, self, request, context):
        out = original(self, request, context)
        command = bridge_one_hot(request.route) if JUDGE_COMMAND == "bridge" else command_from_route(request.route)
        inputs = _session_inputs(request.session_uuid)
        with _inputs_lock:
            inputs.command = np.asarray(command, np.float32)
        return out

    @_wrap("close_session")
    def _close(original, self, request, context):
        with _inputs_lock:
            _inputs.pop(request.session_uuid, None)
        return original(self, request, context)

    @_wrap("_plan")
    def _plan(original, self, policy, session, session_uuid):
        xy = original(self, policy, session, session_uuid)
        _judged.substituted = False
        if xy.shape != (8, 2) or policy.policy_config.trajectory_interval_us != 500_000:
            return xy
        inputs = _session_inputs(session_uuid)
        with _inputs_lock:
            common = set.intersection(*(set(inputs.frames[c]) for c in JUDGE_CAMERAS))
            anchor_us = session.scene_api.newest_timestamp_us
            t = anchor_us if anchor_us in common else (max(common) if common else None)
            images = {c: inputs.frames[c][t] for c in JUDGE_CAMERAS} if t is not None else None
            command = inputs.command
            status = np.concatenate([command if command is not None else unknown,
                                     inputs.velocity, inputs.acceleration]).astype(np.float32)
        if images is None:
            LOG.warning("judge skipped for %s: no common CAM_L0/F0/R0 frame", session_uuid)
            return xy
        with _judge_lock:
            res = _judge.judge(images, status, _plan_with_yaw(xy))
        LOG.info("judge %s", json.dumps({"session": session_uuid, "anchor": t == anchor_us, **res["record"]}))
        if res["trajectory"] is None:
            return xy
        _judged.substituted = True
        return np.asarray(res["trajectory"], np.float64)[:, :2]


if __name__ == "__main__":
    LOG.warning("garage add-ons: time scale %s (only below %s deg heading change, skip judged %s), judge %r",
                TIME_SCALE, MAX_TURN_DEG, TS_SKIP_JUDGED, JUDGE)
    if JUDGE == "gtrs":
        from wajepa_challenge.judge import GtrsJudge
        _judge = GtrsJudge(os.environ["GARAGE_GTRS_CHECKPOINT"], os.environ["GARAGE_GTRS_VOCAB"],
                           device=os.environ.get("GARAGE_JUDGE_DEVICE", "cuda"),
                           margin=float(os.environ.get("GARAGE_JUDGE_MARGIN", "1")),
                           radius=float(os.environ.get("GARAGE_JUDGE_RADIUS", "1")),
                           stall_m=float(os.environ.get("GARAGE_JUDGE_STALL_M", "0")),       # 0 = off
                           stall_margin=float(os.environ.get("GARAGE_JUDGE_STALL_MARGIN", "1")),
                           stall_min_prob=float(os.environ.get("GARAGE_JUDGE_STALL_MIN_PROB", "0.9")),
                           stall_min_move_m=float(os.environ.get("GARAGE_JUDGE_STALL_MIN_MOVE_M", "3")))
        _install_judge()
    evaluate.main()
