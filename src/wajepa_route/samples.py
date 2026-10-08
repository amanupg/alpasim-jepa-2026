"""WA-JEPA training samples from nuPlan logs in 123D format (kesai-labs/nuplan), for the route-conditioning pilot.

One sample per anchor frame, matching what our AlpaSim driver feeds WA-JEPA (wajepa_challenge/preprocessing.py):
  * images [12, 4, 256, 512, 3] uint8: 4 history frames (t0-1.5 s .. t0) then 8 future frames (t0+0.5 .. t0+4 s),
    0.5 s apart, cameras l0, f0, r0, b0, full frame resized with INTER_AREA. Future frames are only used to make
    the frozen teacher's future-scene targets, as in WA-JEPA's own training.
  * history_trajectory [4, 3]: rear-axle (x, y, yaw) at t0-1.5 .. t0 relative to t0 (last row is zeros).
  * future_trajectory [8, 3]: rear-axle poses at t0+0.5 .. t0+4 s relative to t0 (the training target).
  * ego_status [8]: command one-hot (organisers' rule on the route ahead, as the driver) + vx, vy, ax, ay (ego frame).
  * target_point [2]: the route 45 m ahead of the anchor's route progress, rear-axle frame (py123d's
    get_target_points, the same point the py123d policy is conditioned on).
Scenes come from py123d's own scene builder with the py123d training plausibility filters.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
from py123d.datatypes.sensors.base_camera import CameraID

from py123d_garage.py123d_help.scene_builders import VerboseThreadPoolExecutor, build_scene_builder
from py123d_garage.py123d_help.scene_filters.scene_filter import GarageSceneFilter
from py123d_garage.py123d_help.scene_readers.ego_state import sample_ego_se2
from py123d_garage.py123d_help.scene_readers.target_points import get_target_points

CAMERAS = (CameraID.PCAM_L0, CameraID.PCAM_F0, CameraID.PCAM_R0, CameraID.PCAM_B0)   # WA-JEPA's slot order
INPUT_H, INPUT_W = 256, 512
STEP_US = 500_000
HISTORY_OFFSETS_US = [-1_500_000, -1_000_000, -500_000, 0]
FUTURE_OFFSETS_US = [STEP_US * k for k in range(1, 9)]
TARGET_DISTANCE_M = 45.0
FRAME_TOLERANCE_US = 60_000          # cameras run at 10 Hz in 123D; a frame must sit within 60 ms of its slot


def scene_filter(split: str, anchor_spacing_s: float, log_names: list[str] | None = None) -> GarageSceneFilter:
    cams = [f"camera.{c.name.lower()}" for c in CAMERAS]
    return GarageSceneFilter(
        split_names=[split],
        log_names=log_names,
        future_duration_s=4.0,
        history_duration_s=1.5,
        min_remaining_route_m=TARGET_DISTANCE_M,
        custom_anchor_filter_fns=[
            "py123d_garage.py123d_help.scene_filters.filter_fns.plausibility:plausible_ego_motion",
            "py123d_garage.py123d_help.scene_filters.filter_fns.plausibility:plausible_route",
        ],
        timestamp_threshold_s=anchor_spacing_s,
        required_scene_modalities=["ego_state_se3", *cams],
    )


def list_scenes(data_root: str, split: str, anchor_spacing_s: float = 2.0, log_names: list[str] | None = None,
                executor=None):
    builder = build_scene_builder(data_root, lazy=True)
    filt = scene_filter(split, anchor_spacing_s, log_names).to_py123d_scene_filter()
    return builder.get_scenes(filter=filt, executor=executor or VerboseThreadPoolExecutor())   # as build_cache.py


def _relative(origin_xyyaw: np.ndarray, poses_xyyaw: np.ndarray) -> np.ndarray:
    ox, oy, oh = origin_xyyaw
    c, s = math.cos(-oh), math.sin(-oh)
    p = np.asarray(poses_xyyaw, np.float64).copy()
    p[:, 0] -= ox; p[:, 1] -= oy; p[:, 2] -= oh
    p[:, :2] = p[:, :2] @ np.array([[c, -s], [s, c]]).T
    p[:, 2] = np.arctan2(np.sin(p[:, 2]), np.cos(p[:, 2]))
    return p.astype(np.float32)


def command_one_hot_from_points(route_xy_ego: np.ndarray, lateral_threshold_m: float = 2.0,
                                min_lookahead_m: float = 5.0) -> np.ndarray:
    """The organisers' rule (wajepa_challenge.navigation.command_from_route) on ego-frame route points:
    the first point at least 5 m away decides LEFT (y > 2 m) / RIGHT (y < -2 m) / STRAIGHT."""
    out = np.zeros(4, np.float32)
    far = [p for p in route_xy_ego if math.hypot(p[0], p[1]) >= min_lookahead_m]
    if not far:
        out[1] = 1.0
    elif far[0][1] > lateral_threshold_m:
        out[0] = 1.0
    elif far[0][1] < -lateral_threshold_m:
        out[2] = 1.0
    else:
        out[1] = 1.0
    return out


@dataclass
class Sample:
    images: np.ndarray            # [12, 4, 256, 512, 3] uint8
    history_trajectory: np.ndarray
    future_trajectory: np.ndarray
    ego_status: np.ndarray
    target_point: np.ndarray
    log_name: str
    timestamp_us: int


SKIP_REASONS: dict[str, int] = {}


def _skip(reason: str) -> None:
    SKIP_REASONS[reason] = SKIP_REASONS.get(reason, 0) + 1
    return None


def build_sample(scene) -> Sample | None:
    """None when a frame or pose is missing near its slot (the filter checks presence, not timing);
    the reason is counted in SKIP_REASONS."""
    ego0 = scene.get_ego_state_se3_at_iteration(0)
    if ego0 is None or ego0.dynamic_state_se3 is None:
        return _skip("no ego state or dynamics")
    t0 = int(ego0.timestamp.time_us)
    origin = ego0.rear_axle_se2.array.astype(np.float64)

    hist = []
    for dt in HISTORY_OFFSETS_US:
        e = scene.get_ego_state_se3_at_timestamp(t0 + dt, criteria="nearest")
        if e is None or abs(int(e.timestamp.time_us) - (t0 + dt)) > FRAME_TOLERANCE_US:
            return _skip("history ego pose")
        hist.append(e.rear_axle_se2.array)
    history = _relative(origin, np.array(hist))

    future = sample_ego_se2(scene, num_steps=8, interval_us=STEP_US, relative_to_anchor=True).pose_se2_array
    future = np.asarray(future, np.float32)
    if future.shape != (8, 3) or not np.isfinite(future).all():
        return _skip("future trajectory")

    # The route polyline ahead, in the anchor's rear-axle frame, for the drive command (1 m spacing). The filter
    # guarantees 45 m of route; the command rule only needs the first point beyond 5 m.
    tp = get_target_points(scene, [float(d) for d in range(1, int(TARGET_DISTANCE_M))] + [TARGET_DISTANCE_M])
    route_ahead, target = tp[:-1], tp[-1]
    command = command_one_hot_from_points(route_ahead)
    dyn = ego0.dynamic_state_se3
    ego_status = np.concatenate([command, np.asarray(dyn.velocity_2d.array, np.float32),
                                 np.asarray(dyn.acceleration_2d.array, np.float32)]).astype(np.float32)

    images = np.empty((12, 4, INPUT_H, INPUT_W, 3), np.uint8)
    for ti, dt in enumerate(HISTORY_OFFSETS_US + FUTURE_OFFSETS_US):
        for ci, cam in enumerate(CAMERAS):
            frame = scene.get_camera_at_timestamp(t0 + dt, cam, criteria="nearest")
            if frame is None:
                return _skip(f"no {cam.name} frame")
            if abs(int(frame.timestamp.time_us) - (t0 + dt)) > FRAME_TOLERANCE_US:
                return _skip(f"{cam.name} frame {(int(frame.timestamp.time_us) - (t0 + dt)) // 1000} ms off slot")
            images[ti, ci] = cv2.resize(np.ascontiguousarray(frame.image), (INPUT_W, INPUT_H),
                                        interpolation=cv2.INTER_AREA)
    return Sample(images, history, future, ego_status, np.asarray(target, np.float32), scene.log_name, t0)
