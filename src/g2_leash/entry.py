"""py123d_garage v0.2.2 AlpaSim driver with a lateral leash to the route (last-slot idea, LEDGER 2026-11-14).
Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0) after wrapping `GarageDriver._plan`.

Idea read from a public board entry name (CQUPT 'geo1134-turngate30-pathonly-leash', 11-14), method our own guess:
  - reference path: a cubic Hermite curve from the ego (current heading) onto the served route (which starts ~40 m
    ahead, recorded path), then the route;
  - leash: each planned pose keeps its arc length (so the model's speed profile, 'path only'), and its lateral offset
    from the reference is clamped to +- G2_LEASH_M metres;
  - turn gate: only when the reference turns by less than G2_LEASH_GATE_DEG within the plan's reach; in turns the
    model's plan is served as is. No route -> plan unchanged.
"""
from __future__ import annotations

import logging
import os

import numpy as np

from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service

LOG = logging.getLogger("g2_leash")
LEASH = float(os.environ.get("G2_LEASH_M", "0.5"))
GATE = float(os.environ.get("G2_LEASH_GATE_DEG", "30"))
VMIN = float(os.environ.get("G2_LEASH_VMIN", "1.0"))
STEP = 0.5


def to_rig(xy_local: np.ndarray, ego_pose_local: np.ndarray) -> np.ndarray:
    c, s = np.cos(ego_pose_local[3]), np.sin(ego_pose_local[3])
    d = xy_local - ego_pose_local[None, :2]
    return np.stack([c * d[:, 0] + s * d[:, 1], -s * d[:, 0] + c * d[:, 1]], axis=1)


def resample(poly: np.ndarray, step: float = STEP) -> np.ndarray:
    seg = np.hypot(*np.diff(poly, axis=0).T)
    keep = np.concatenate([[True], seg > 1e-6])
    poly = poly[keep]
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(poly, axis=0).T))])
    q = np.arange(0.0, s[-1] + 1e-9, step)
    return np.stack([np.interp(q, s, poly[:, 0]), np.interp(q, s, poly[:, 1])], axis=1)


def reference(route: np.ndarray) -> np.ndarray | None:
    """Ego (heading +x) -> Hermite onto route[0] with the route's tangent -> route; resampled every STEP m."""
    if len(route) < 2:
        return None
    p1 = route[0]
    t1 = route[1] - route[0]
    n1 = np.hypot(*t1)
    if n1 < 1e-6:
        return None
    chord = max(np.hypot(*p1), 1.0)
    m0, m1 = np.array([chord, 0.0]), t1 / n1 * chord
    u = np.linspace(0.0, 1.0, max(int(chord / STEP), 2))[:, None]
    h00, h10, h01, h11 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u, -2 * u**3 + 3 * u**2, u**3 - u**2
    herm = h10 * m0 + h01 * p1 + h11 * m1   # h00 * p0 with p0 = 0
    return resample(np.vstack([herm, route[1:]]))


def heading_change_deg(ref: np.ndarray, reach_m: float) -> float:
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(ref, axis=0).T))])
    pts = ref[s <= max(reach_m, 2 * STEP)]
    if len(pts) < 2:
        return 0.0
    yaw = np.unwrap(np.arctan2(*np.diff(pts, axis=0).T[::-1]))
    return float(np.degrees(np.max(np.abs(yaw))))


def frenet(ref: np.ndarray, pts: np.ndarray):
    """Arc length, signed lateral (left +) and the segment index of each point's projection onto the polyline."""
    seg = np.diff(ref, axis=0)
    L = np.hypot(*seg.T)
    s0 = np.concatenate([[0.0], np.cumsum(L)])
    d = pts[:, None, :] - ref[None, :-1, :]
    t = np.clip((d * seg[None]).sum(-1) / L[None] ** 2, 0.0, 1.0)
    proj = ref[None, :-1, :] + t[..., None] * seg[None]
    dist = np.hypot(*(pts[:, None, :] - proj).transpose(2, 0, 1))
    i = dist.argmin(axis=1)
    k = np.arange(len(pts))
    tang = seg[i] / L[i, None]
    rel = pts - proj[k, i]
    lat = tang[:, 0] * rel[:, 1] - tang[:, 1] * rel[:, 0]
    return s0[i] + t[k, i] * L[i], lat, i, tang


def leashed(poses: np.ndarray, route: np.ndarray, leash: float = LEASH, gate: float = GATE) -> np.ndarray:
    ref = reference(route)
    if ref is None:
        return poses
    reach = float(np.hypot(*poses[-1, :2])) + 5.0
    if heading_change_deg(ref, reach) >= gate:
        return poses
    s, lat, i, tang = frenet(ref, poses[:, :2])
    lat_c = np.clip(lat, -leash, leash)
    if np.allclose(lat_c, lat):
        return poses
    normal = np.stack([-tang[:, 1], tang[:, 0]], axis=1)
    xy = poses[:, :2] + (lat_c - lat)[:, None] * normal
    full = np.vstack([np.zeros((1, 2)), xy])
    d = np.diff(full, axis=0)
    yaw = np.arctan2(d[:, 1], d[:, 0])
    small = np.hypot(*d.T) < 0.05            # near standstill: keep the model's yaw
    yaw[small] = poses[small, 2]
    return np.column_stack([xy, yaw])


def install() -> None:
    original = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        poses = original(self, policy, session, session_uuid)
        try:
            route = session.route_xy_local
            if (poses.shape == (64, 3) and route is not None and len(route) >= 2 and session.ego_pose_local is not None
                    and float(session.speed_mps) >= VMIN):
                return leashed(poses, to_rig(np.asarray(route, dtype=float), session.ego_pose_local))
        except Exception:  # a failure here must fall back to the model's plan
            LOG.exception("leash failed for %s", session_uuid)
        return poses

    driver_service.GarageDriver._plan = _plan


if __name__ == "__main__":
    LOG.warning("g2 leash: M=%.2f gate_deg=%.0f vmin=%.1f", LEASH, GATE, VMIN)
    install()
    evaluate.main()
