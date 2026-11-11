"""py123d_garage v0.2.2 AlpaSim driver with a stall nudge (candidate fix 1), without modifying its code.

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0) after wrapping `TransfuserPolicy.forward`
(to read the step's own detected boxes) and `GarageDriver._plan` (to change the plan when the nudge fires).

Trigger (chosen in shadow mode, LEDGER 2026-11-10; same rule as src/analysis/shadow_triggers.fix1_fires): the ego is
slow (< G2_NUDGE_V m/s), the plan waits (pose at 2.0 s is < 1 m away), and the model's own boxes show nothing in the
way: no box within 25 m along the route corridor (|lateral| < 2 m), no moving vehicle or two-wheeler crossing within
30 m, no static object (sign, barrier, cone, generic) within 15 m ahead and 8 m to the side. The nudge acts only once
the trigger has held for G2_NUDGE_K plans in a row (default 3, 1.5 s); after the first nudge in a session it may act
again on any single firing plan (latched), so the car is not left to stall again after one step.

Action, G2_NUDGE_MODE:
  A  wait-then-go plans only (the plan moves >= 3 m by 6.4 s after waiting >= 0.5 s): drop the waiting prefix so the
     model's own motion starts now (as v8 start-now). Plans that stay stopped are left alone.
  B  as A, and for plans that stay stopped: a gentle start along the route (accelerate at G2_NUDGE_ACC m/s^2 up to
     G2_NUDGE_VMAX m/s), only if the route heads within 20 deg of straight ahead over its first 10 m.
     G2_NUDGE_CREEP_FROM_REST=1: the gentle start only while the ego has not yet reached G2_NUDGE_V in the session
     (on NuRec, creeping during mid-scene stops, likely at lights the trigger cannot see, caused 2 new zeros).
Off unless G2_NUDGE_MODE is A or B. Firings are logged to G2_NUDGE_LOG (a directory) if set. The scene id comes from
the local debug info only (absent in benchmark runs); it is used for log names, never to drive.
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading

import numpy as np

from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service
from py123d_garage.policy.transfuser import transfuser_policy

LOG = logging.getLogger("g2_nudge")
MODE = os.environ.get("G2_NUDGE_MODE", "").upper()
K = int(os.environ.get("G2_NUDGE_K", "3"))
V = float(os.environ.get("G2_NUDGE_V", "0.5"))
W = 1.0                     # plan "waits": pose at 2.0 s closer than this
D, C, R, S = 25.0, 2.0, 30.0, 15.0
ACC = float(os.environ.get("G2_NUDGE_ACC", "1.0"))
VMAX = float(os.environ.get("G2_NUDGE_VMAX", "4.0"))
LATCH = os.environ.get("G2_NUDGE_LATCH", "1") == "1"
CREEP_FROM_REST = os.environ.get("G2_NUDGE_CREEP_FROM_REST", "0") == "1"   # creep only if the ego has not moved yet
LOGDIR = os.environ.get("G2_NUDGE_LOG", "")
START_D, START_WAIT_S, MOVE_M, DT = 3.0, 0.5, 0.3, 0.1
_tls = threading.local()
_lock = threading.Lock()


def _to_rig(xy_local: np.ndarray, ego: np.ndarray) -> np.ndarray:
    c, s = np.cos(ego[3]), np.sin(ego[3])
    d = xy_local - ego[None, :2]
    return np.stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]], axis=1)


def _resample(poly: np.ndarray, step_m: float = 2.0, max_m: float = 80.0) -> np.ndarray:
    if len(poly) < 2:
        return poly
    seg = np.hypot(*np.diff(poly, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    q = np.arange(0.0, min(s[-1], max_m) + 1e-6, step_m)
    return np.stack([np.interp(q, s, poly[:, 0]), np.interp(q, s, poly[:, 1])], axis=1)


def _corridor(route: np.ndarray, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Arc length along the walk (ego, then route) and lateral distance of each point (straight ahead if no route).
    The served route often starts well ahead of the ego, so the walk from the ego onto it is used, as the driver does
    for its target points."""
    if len(route):
        route = np.vstack([np.zeros((1, 2)), route])
    if len(route) < 2:
        return pts[:, 0], np.abs(pts[:, 1])
    seg = np.diff(route, axis=0)
    seglen = np.hypot(seg[:, 0], seg[:, 1]) + 1e-9
    s0 = np.concatenate([[0.0], np.cumsum(seglen)])
    best_d, best_s = np.full(len(pts), np.inf), np.zeros(len(pts))
    for i in range(len(seg)):
        t = np.clip(((pts - route[i]) @ seg[i]) / seglen[i] ** 2, 0, 1)
        d = np.hypot(*(pts - (route[i] + t[:, None] * seg[i])).T)
        better = d < best_d
        best_d[better], best_s[better] = d[better], s0[i] + t[better] * seglen[i]
    return best_s, best_d


def fires(speed: float, poses: np.ndarray, boxes: np.ndarray, route: np.ndarray) -> bool:
    if speed >= V or math.hypot(poses[19, 0], poses[19, 1]) >= W:
        return False
    if len(boxes):
        s, lat = _corridor(route, boxes[:, :2])
        if np.any((boxes[:, 0] > -1.0) & (s < D) & (lat < C)):
            return False
        cls, spd, yaw = boxes[:, 6], boxes[:, 5], boxes[:, 4]
        crossing = np.isin(cls, (0, 2)) & (np.abs(spd) > 1.0) & (np.abs(np.sin(yaw)) > math.sin(math.radians(30)))
        if np.any(crossing & (np.hypot(boxes[:, 0], boxes[:, 1]) < R) & (boxes[:, 0] > -5)):
            return False
        if np.any((cls == 3) & (boxes[:, 0] > 0) & (boxes[:, 0] < S) & (np.abs(boxes[:, 1]) < 8)):
            return False
    return True


def start_now(poses: np.ndarray) -> np.ndarray | None:
    """The plan with its waiting prefix dropped, or None if it is not wait-then-go (as src/g2_addons)."""
    disp = np.hypot(poses[:, 0], poses[:, 1])
    if disp[-1] < START_D or disp[0] > MOVE_M:
        return None
    shift = int(np.argmax(disp > MOVE_M)) - 1
    if shift * DT < START_WAIT_S:
        return None
    kept = poses[shift:]
    step = kept[-1] - kept[-2]
    return np.vstack([kept, kept[-1] + step * np.arange(1, shift + 1)[:, None]])


def creep(route: np.ndarray, speed: float) -> np.ndarray | None:
    """64 poses along the walk from the ego onto the route: accelerate at ACC up to VMAX. None unless the route is
    there and the walk heads within 20 deg of straight ahead over its first 10 m (no creeping into a turn)."""
    if len(route) < 2:
        return None
    walk = np.vstack([np.zeros((1, 2)), route])
    seg = np.hypot(*np.diff(walk, axis=0).T)
    s_walk = np.concatenate([[0.0], np.cumsum(seg)])
    p10 = np.array([np.interp(10.0, s_walk, walk[:, 0]), np.interp(10.0, s_walk, walk[:, 1])])
    if abs(math.atan2(p10[1], p10[0])) > math.radians(20):
        return None
    t = DT * np.arange(1, 65)
    v0 = max(speed, 0.0)
    t_acc = max(VMAX - v0, 0.0) / ACC
    q = np.where(t < t_acc, v0 * t + 0.5 * ACC * t ** 2, v0 * t_acc + 0.5 * ACC * t_acc ** 2 + VMAX * (t - t_acc))
    if q[-1] > s_walk[-1]:
        return None
    x, y = np.interp(q, s_walk, walk[:, 0]), np.interp(q, s_walk, walk[:, 1])
    ds = 0.5
    yaw = np.arctan2(np.interp(q + ds, s_walk, walk[:, 1]) - np.interp(q - ds, s_walk, walk[:, 1]),
                     np.interp(q + ds, s_walk, walk[:, 0]) - np.interp(q - ds, s_walk, walk[:, 0]))
    return np.column_stack([x, y, yaw])


def _log(session, session_uuid: str, rec: dict) -> None:
    if not LOGDIR:
        return
    name = re.sub(r"[^A-Za-z0-9._-]", "_", f"{session.scene_id}__{session_uuid}")
    with _lock, open(os.path.join(LOGDIR, name + ".jsonl"), "a") as f:
        f.write(json.dumps(rec) + "\n")


def install() -> None:
    forward = transfuser_policy.TransfuserPolicy.forward

    def _forward(self, *args, **kwargs):
        predictions = forward(self, *args, **kwargs)
        _tls.predictions = predictions
        return predictions

    transfuser_policy.TransfuserPolicy.forward = _forward
    original = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        _tls.predictions = None
        poses = original(self, policy, session, session_uuid)
        try:
            return _nudge(session, session_uuid, poses)
        except Exception:  # a failure here must fall back to the model's plan
            LOG.exception("nudge failed for %s", session_uuid)
            return poses

    driver_service.GarageDriver._plan = _plan


def _nudge(session, session_uuid: str, poses: np.ndarray) -> np.ndarray:
    pred = getattr(_tls, "predictions", None)
    if MODE not in ("A", "B") or poses.shape != (64, 3) or session.ego_pose_local is None:
        return poses
    boxes = np.zeros((0, 8))
    if pred is not None and pred.boxes is not None:
        boxes = np.asarray(pred.boxes.pred_bounding_box_vehicle_system[0], dtype=np.float64).reshape(-1, 8)
    route_local = session.route_xy_local
    route = _resample(_to_rig(np.asarray(route_local)[:, :2], session.ego_pose_local)) if len(route_local) else np.zeros((0, 2))
    speed = float(session.speed_mps)
    session._g2_vmax = max(getattr(session, "_g2_vmax", 0.0), speed)
    hit = fires(speed, poses, boxes, route)
    run = getattr(session, "_g2_nudge_run", 0) + 1 if hit else 0
    session._g2_nudge_run = run
    latched = LATCH and getattr(session, "_g2_nudged", False)
    if not hit or (run < K and not latched):
        return poses
    new, kind = start_now(poses), "drop_wait"
    if new is None and MODE == "B" and not (CREEP_FROM_REST and session._g2_vmax >= V):
        new, kind = creep(route, speed), "creep"
    plan_no = int(session.num_plans) - 1
    _log(session, session_uuid, {"plan": plan_no, "speed": speed, "run": run, "kind": kind if new is not None else "none"})
    if new is None:
        return poses
    session._g2_nudged = True
    LOG.info("nudge %s plan %d: %s after %d firing plans", session_uuid, plan_no, kind, run)
    return new


if __name__ == "__main__":
    if LOGDIR:
        os.makedirs(LOGDIR, exist_ok=True)
    LOG.warning("g2 nudge: mode=%s K=%d V=%.2f acc=%.1f vmax=%.1f latch=%d creep_from_rest=%d log=%s",
                MODE or "off", K, V, ACC, VMAX, LATCH, CREEP_FROM_REST, LOGDIR or "-")
    install()
    evaluate.main()
