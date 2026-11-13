"""py123d_garage v0.2.2 AlpaSim driver that records on-policy training samples for a DAgger-style fine-tune of W1.

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0) after wrapping three methods:
  - `GarageDriver.submit_recording_ground_truth`: keeps the human (logged) ego trajectory the runtime sends each step
    when `runtime.simulation_config.send_recording_ground_truth=true` (local data collection only; the challenge
    config never sends it, and the submitted driver never reads it);
  - `TransfuserPolicy.forward`: keeps the model inputs (features, navigation) of the current plan;
  - `GarageDriver._plan`: saves one sample per plan (inputs, the model's plan, the human trajectory in the current
    rig frame) to G2_DAGGER_DIR/<scene>__<session>__<plan>.pt and, with G2_DAGGER_NOISE > 0, serves a perturbed
    plan so the rollout visits states off the model's own path (labels come from the human trajectory, never from
    the perturbed plan).

Noise (per plan, with probability G2_DAGGER_NOISE): a lateral offset U(-G2_DAGGER_LAT, +G2_DAGGER_LAT) m ramped in
linearly over the first 2 s of the plan, and a time scale U(1-G2_DAGGER_SPD, 1+G2_DAGGER_SPD) (speed factor). Seeded
by session id and G2_DAGGER_SEED, so reruns repeat.
The scene id comes from local debug info only; it names files, never drives.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import threading

import numpy as np
import torch

from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service
from py123d_garage.policy.transfuser import transfuser_policy

LOG = logging.getLogger("g2_dagger")
OUT = os.environ.get("G2_DAGGER_DIR", "")
NOISE = float(os.environ.get("G2_DAGGER_NOISE", "0"))
LAT = float(os.environ.get("G2_DAGGER_LAT", "0.8"))
SPD = float(os.environ.get("G2_DAGGER_SPD", "0.2"))
SEED = os.environ.get("G2_DAGGER_SEED", "0")
DT = 0.1
_tls = threading.local()
_write_lock = threading.Lock()


def _cpu(x):
    return x.apply(lambda t: t.detach().to("cpu")) if x is not None else None


def perturb(poses: np.ndarray, lat: float, scale: float) -> np.ndarray:
    """The plan retimed by `scale` (speed factor) and shifted `lat` m to its left, ramped in over 2 s."""
    n = len(poses)
    full = np.vstack([np.zeros((1, 3)), poses])
    t = DT * np.arange(n + 1)
    q = np.clip(t[1:] * scale, 0, t[-1])
    yaw = np.unwrap(full[:, 2])
    x, y = (np.interp(q, t, full[:, i]) for i in (0, 1))
    h = np.interp(q, t, yaw)
    extra = t[1:] * scale - q            # beyond the plan's end: continue at the last velocity
    if extra.max() > 0:
        v = (full[-1, :2] - full[-2, :2]) / DT
        x, y = x + v[0] * extra, y + v[1] * extra
    ramp = np.minimum(1.0, t[1:] / 2.0) * lat
    x, y = x - ramp * np.sin(h), y + ramp * np.cos(h)
    h = (h + np.pi) % (2 * np.pi) - np.pi
    return np.column_stack([x, y, h])


def install() -> None:
    forward = transfuser_policy.TransfuserPolicy.forward

    def _forward(self, features, navigation, *args, **kwargs):
        _tls.inputs = (_cpu(features), _cpu(navigation))
        return forward(self, features, navigation, *args, **kwargs)

    transfuser_policy.TransfuserPolicy.forward = _forward

    def _gt(self, request, context):
        try:
            session = self._get_session(request.session_uuid, context)
            gt = request.ground_truth
            poses = gt.trajectory.poses
            arr = np.array([[p.timestamp_us, p.pose.vec.x, p.pose.vec.y, driver_service._yaw_from_quaternion(p.pose.quat)]
                            for p in poses], dtype=np.float64)
            session._g2_gt = (int(gt.timestamp_us), arr)
        except Exception:
            LOG.exception("ground truth capture failed")
        return driver_service.common_pb2.Empty()

    driver_service.GarageDriver.submit_recording_ground_truth = _gt
    original = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        _tls.inputs = None
        poses = original(self, policy, session, session_uuid)
        try:
            _save(session, session_uuid, poses)
        except Exception:  # recording must never change driving
            LOG.exception("dagger save failed for %s", session_uuid)
        if NOISE > 0 and poses.shape == (64, 3):
            key = f"{SEED}:{session_uuid}:{session.num_plans}"
            rng = np.random.default_rng(int(hashlib.md5(key.encode()).hexdigest()[:8], 16))
            if rng.random() < NOISE:
                return perturb(poses, rng.uniform(-LAT, LAT), rng.uniform(1 - SPD, 1 + SPD))
        return poses

    driver_service.GarageDriver._plan = _plan


def _save(session, session_uuid: str, poses: np.ndarray) -> None:
    inputs = getattr(_tls, "inputs", None)
    gt = getattr(session, "_g2_gt", None)
    if not OUT or inputs is None or gt is None:
        return
    features, navigation = inputs
    step_us, arr = gt
    plan = int(session.num_plans) - 1
    rec = {"features": features, "navigation": navigation, "pred": poses.astype(np.float32),
           "gt_step_us": step_us, "gt": arr, "speed": float(session.speed_mps), "plan": plan,
           "scene": str(session.scene_id), "session": session_uuid}
    name = re.sub(r"[^A-Za-z0-9._-]", "_", f"{session.scene_id}__{session_uuid}__{plan:03d}")
    with _write_lock:
        torch.save(rec, os.path.join(OUT, name + ".pt"))


if __name__ == "__main__":
    if OUT:
        os.makedirs(OUT, exist_ok=True)
    LOG.warning("g2 dagger: recording to %s; noise p=%.2f lat=%.2f spd=%.2f seed=%s", OUT or "(off)", NOISE, LAT, SPD, SEED)
    install()
    evaluate.main()
