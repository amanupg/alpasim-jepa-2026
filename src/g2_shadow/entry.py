"""py123d_garage v0.2.2 AlpaSim driver in shadow mode: logs what the two candidate fixes would see, changes nothing.

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0) unchanged, after wrapping
`TransfuserPolicy.forward` (to keep each step's predictions) and `GarageDriver._plan` (to log them next to the plan).
The served plan is the original one, bit for bit, so a shadow run must reproduce the plain driver's scores.

Logged per plan (one JSON line, G2_SHADOW_DIR/<scene>__<session>.jsonl), all in the rig frame of the current pose
(x forward, y left, metres):
  - speed, acceleration, the 64 planned poses (x, y, yaw), the route ahead (resampled every 2 m, up to 80 m);
  - the model's own confident boxes (x, y, length, width, yaw, speed, class, score); classes 0 vehicle, 1 person,
    2 two-wheeler, 3 static (traffic sign, barrier, cone, generic object);
  - for each planned pose, the model's predicted probability that the ground there is drivable (BEV classes road,
    lane centre line, vehicle), at the pose and 1.0 m to its left and right.
Also per session: the argmax BEV map of every plan (G2_SHADOW_DIR/<scene>__<session>_bev.npz) to check the predicted
road against the true map.

Candidate fix 1 (stall nudge) and fix 2 (off-road guard) are evaluated offline from these logs (src/analysis).
The scene id comes from the local debug info only (absent in benchmark runs); it is used for log names, never to drive.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading

import numpy as np
import torch

from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service
from py123d_garage.policy.transfuser import transfuser_policy

LOG = logging.getLogger("g2_shadow")
OUT = os.environ.get("G2_SHADOW_DIR", "")
DRIVABLE = (1, 3, 5)          # BEV labels: 1 road (lane, intersection, generic drivable), 3 centre line, 5 vehicle
SIDE_M = 1.0                  # lateral offset of the side samples (about half the ego width)
_tls = threading.local()
_write_lock = threading.Lock()


def _to_rig(xy_local: np.ndarray, ego_pose_local: np.ndarray) -> np.ndarray:
    c, s = np.cos(ego_pose_local[3]), np.sin(ego_pose_local[3])
    d = xy_local - ego_pose_local[None, :2]
    return np.stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]], axis=1)


def _resample(poly: np.ndarray, step_m: float = 2.0, max_m: float = 80.0) -> np.ndarray:
    if len(poly) < 2:
        return poly
    seg = np.hypot(*np.diff(poly, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    q = np.arange(0.0, min(s[-1], max_m) + 1e-6, step_m)
    return np.stack([np.interp(q, s, poly[:, 0]), np.interp(q, s, poly[:, 1])], axis=1)


def _drivable_along(prob: np.ndarray, poses: np.ndarray, cfg) -> np.ndarray:
    """(64, 3) drivable probability at each pose and SIDE_M to its left/right; NaN outside the BEV grid."""
    lc = cfg.lidar_config
    h, w = prob.shape
    ppm_x = w / (lc.bev_max_x_m - lc.bev_min_x_m)
    ppm_y = h / (lc.bev_max_y_m - lc.bev_min_y_m)
    out = np.full((len(poses), 3), np.nan)
    for j, off in enumerate((0.0, SIDE_M, -SIDE_M)):
        x = poses[:, 0] - off * np.sin(poses[:, 2])
        y = poses[:, 1] + off * np.cos(poses[:, 2])
        col = np.floor((x - lc.bev_min_x_m) * ppm_x).astype(int)   # column = x (labels._coords_to_pixel)
        row = np.floor((y - lc.bev_min_y_m) * ppm_y).astype(int)   # row = y
        ok = (col >= 0) & (col < w) & (row >= 0) & (row < h)
        out[ok, j] = prob[row[ok], col[ok]]
    return out


def install() -> None:
    forward = transfuser_policy.TransfuserPolicy.forward

    def _forward(self, *args, **kwargs):
        predictions = forward(self, *args, **kwargs)
        _tls.predictions = predictions
        _tls.config = self._config
        return predictions

    transfuser_policy.TransfuserPolicy.forward = _forward
    original = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        _tls.predictions = None
        poses = original(self, policy, session, session_uuid)
        try:
            _log(session, session_uuid, poses)
        except Exception:  # logging must never change driving
            LOG.exception("shadow log failed for %s", session_uuid)
        return poses

    driver_service.GarageDriver._plan = _plan


def _log(session, session_uuid: str, poses: np.ndarray) -> None:
    pred, cfg = getattr(_tls, "predictions", None), getattr(_tls, "config", None)
    if not OUT or pred is None or cfg is None or session.ego_pose_local is None:
        return
    rec = {"plan": int(session.num_plans) - 1, "speed": float(session.speed_mps),
           "acc": float(session.acceleration_mps2), "poses": np.round(poses, 3).tolist()}
    route = session.route_xy_local
    rec["route"] = np.round(_resample(_to_rig(route, session.ego_pose_local)), 2).tolist() if len(route) else []
    boxes = []
    if pred.boxes is not None:
        b = pred.boxes.pred_bounding_box_vehicle_system[0]
        boxes = np.round(b.astype(np.float64), 3).tolist()
    rec["boxes"] = boxes
    bev = None
    if pred.bev_semantic is not None:
        p = torch.softmax(pred.bev_semantic[0].float(), dim=0).cpu().numpy()
        drv = p[list(DRIVABLE)].sum(axis=0)
        rec["drv"] = np.round(_drivable_along(drv, poses, cfg), 3).tolist()
        bev = p.argmax(axis=0).astype(np.uint8)
    name = re.sub(r"[^A-Za-z0-9._-]", "_", f"{session.scene_id}__{session_uuid}")
    with _write_lock:
        with open(os.path.join(OUT, name + ".jsonl"), "a") as f:
            f.write(json.dumps(rec) + "\n")
        if bev is not None:
            store = getattr(session, "_g2_bev", [])
            store.append(bev)
            session._g2_bev = store
            np.savez_compressed(os.path.join(OUT, name + "_bev.npz"), bev=np.stack(store))


if __name__ == "__main__":
    if OUT:
        os.makedirs(OUT, exist_ok=True)
    LOG.warning("g2 shadow mode: logging to %s; plans unchanged", OUT or "(off: G2_SHADOW_DIR unset)")
    install()
    evaluate.main()
