"""Closed-loop data collection around the same py123d_garage v0.2.2 driver (training data only, never submitted).

Runs the submission add-ons of `entry.py` (start-now, G2_START_K) and records, at every plan, the exact inputs the
policy was given (TransfuserFeatures + NavigationConditioning, batch of one), the ego's local pose, speed and time,
and the session's logged ego trajectory, which the runtime sends only when
`runtime.simulation_config.send_recording_ground_truth=true` (a local-collection switch; official runs keep it off and
the submission never reads it). Recovery labels are built offline from these records (src/closed_loop/labels.py).

G2_CAPTURE_DIR: one `<scene>_<session>.pt` per rollout, written at close_session.
G2_PERTURB_P / G2_PERTURB_M: with probability P per plan, the served plan gets a lateral offset ramping to
U(-M, M) metres over 1.5 s (DART-style exploration), so the records include off-log states to recover from. The
record holds the unperturbed plan's inputs; the perturbation only moves later states. Seeded per session.
"""
from __future__ import annotations

import logging
import math
import os
import pathlib
import threading
import zlib

import numpy as np
import torch

from g2_addons import entry
from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service

LOG = logging.getLogger("g2_collect")
CAPTURE_DIR = pathlib.Path(os.environ["G2_CAPTURE_DIR"])
PERTURB_P = float(os.environ.get("G2_PERTURB_P", "0"))
PERTURB_M = float(os.environ.get("G2_PERTURB_M", "1.0"))
RAMP_S = 1.5
_captured = threading.local()        # _plan and policy.forward run on the same thread


def _cpu(bundle) -> dict[str, torch.Tensor]:
    return {name: value[0].detach().cpu() for name, value in vars(bundle).items() if isinstance(value, torch.Tensor)}


def _gt_local(session) -> dict[str, np.ndarray] | None:
    gt = getattr(session, "_g2_gt_rig", None)
    if gt is None or session.ego_pose_local is None:
        return None
    x, y, _, yaw = session.ego_pose_local
    c, s = math.cos(yaw), math.sin(yaw)
    xy = gt["xy"] @ np.array([[c, s], [-s, c]]) + [x, y]       # rig -> local, as plan.rig_to_local_xy
    return {"timestamps_us": gt["timestamps_us"], "xy": xy, "yaw": gt["yaw"] + yaw, "received_us": gt["received_us"]}


def install() -> None:
    entry.install()                                            # start-now first, exactly as in the submission
    planned = driver_service.GarageDriver._plan

    def _forward_capturing(original_forward):
        def forward(features, navigation):
            if getattr(_captured, "on", False):
                _captured.features, _captured.navigation = _cpu(features), _cpu(navigation)
            return original_forward(features, navigation)
        return forward

    def _plan(self, policy, session, session_uuid):
        if not getattr(policy, "_g2_capturing", False):
            policy.forward = _forward_capturing(policy.forward)
            policy._g2_capturing = True
        _captured.on, _captured.features, _captured.navigation = True, None, None
        try:
            poses = planned(self, policy, session, session_uuid)
        finally:
            _captured.on = False
        if not hasattr(session, "_g2_records"):
            session._g2_records, session._g2_gt_local = [], None
            session._g2_rng = np.random.default_rng(zlib.crc32(session_uuid.encode()))
        if session._g2_gt_local is None:
            session._g2_gt_local = _gt_local(session)
        offset_m = 0.0
        if PERTURB_P > 0 and poses.shape == (64, 3) and session._g2_rng.random() < PERTURB_P:
            offset_m = float(session._g2_rng.uniform(-PERTURB_M, PERTURB_M))
            t = np.arange(1, 65) * entry.DT_S
            poses = poses.copy()
            poses[:, 1] += offset_m * np.clip(t / RAMP_S, 0.0, 1.0)
        session._g2_records.append({
            "features": _captured.features, "navigation": _captured.navigation,
            "ego_pose_local": np.array(session.ego_pose_local, dtype=np.float64),
            "speed_mps": float(session.speed_mps), "acceleration_mps2": float(session.acceleration_mps2),
            "anchor_us": int(session.scene_api.newest_timestamp_us), "served_poses": np.asarray(poses, np.float32),
            "perturb_m": offset_m,
        })
        return poses

    original_gt = driver_service.GarageDriver.submit_recording_ground_truth

    def submit_recording_ground_truth(self, request, context):
        session = self._get_session(request.session_uuid, context)
        poses = request.ground_truth.trajectory.poses
        if poses:                    # latest step's copy, so the rig frame matches the ego pose of the next plan
            session._g2_gt_rig = {
                "timestamps_us": np.array([p.timestamp_us for p in poses], dtype=np.int64),
                "xy": np.array([[p.pose.vec.x, p.pose.vec.y] for p in poses], dtype=np.float64),
                "yaw": np.array([driver_service._yaw_from_quaternion(p.pose.quat) for p in poses], dtype=np.float64),
                "received_us": int(request.ground_truth.timestamp_us),
            }
        return original_gt(self, request, context)

    original_close = driver_service.GarageDriver.close_session

    def close_session(self, request, context):
        session = self._sessions.get(request.session_uuid)
        if session is not None and getattr(session, "_g2_records", None):
            CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
            out = CAPTURE_DIR / f"{session.scene_id}_{request.session_uuid}.pt"
            torch.save({"scene_id": session.scene_id, "session": request.session_uuid,
                        "gt_local": session._g2_gt_local, "records": session._g2_records}, out)
            LOG.info("captured %d plans of %s -> %s (gt %s)", len(session._g2_records), session.scene_id, out.name,
                     "yes" if session._g2_gt_local is not None else "MISSING")
        return original_close(self, request, context)

    driver_service.GarageDriver._plan = _plan
    driver_service.GarageDriver.submit_recording_ground_truth = submit_recording_ground_truth
    driver_service.GarageDriver.close_session = close_session


if __name__ == "__main__":
    LOG.warning("g2 collect: start-now K=%d, capture -> %s, perturb p=%.2f m=%.1f",
                entry.START_K, CAPTURE_DIR, PERTURB_P, PERTURB_M)
    install()
    evaluate.main()
