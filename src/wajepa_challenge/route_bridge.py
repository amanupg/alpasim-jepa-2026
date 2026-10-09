"""NAVSIM-style drive command from the AlpaSim route ("route bridge").

NAVSIM (OpenScene) labels the command from the route centreline: the point s = 20 m ahead of the ego
along the route is LEFT / RIGHT if its lateral offset exceeds +/- 2 m, otherwise STRAIGHT (NAVSIM
paper and supplementary). The AlpaSim nuPlan track sends only the route ~40-80 m ahead
(`route_start_offset_m: 40`), so the organisers' sample rule (first waypoint >= 5 m, |y| > 2 m)
reads the lateral offset ~40 m out: earlier and larger than the label WA-JEPA was trained with.
Here the missing first stretch is bridged with a cubic Hermite curve from the ego (heading +x)
to the first route waypoint (heading along the route), and NAVSIM's rule is applied at s = 20 m.
Waypoints are in the rig frame (x forward, y left), as the organisers' rule assumes.
"""
from __future__ import annotations

import numpy as np

from .navigation import DriveCommand, command_one_hot

S_LOOKAHEAD_M = 20.0
LATERAL_THRESHOLD_M = 2.0


def bridged_route(waypoints_xy: np.ndarray, samples: int = 32) -> np.ndarray:
    """Ego (0, 0) + Hermite bridge to the first waypoint + the route itself, as an [m, 2] polyline."""
    p = np.asarray(waypoints_xy, np.float64).reshape(-1, 2)
    p0, p1 = np.zeros(2), p[0]
    chord = float(np.linalg.norm(p1))
    t0 = np.array([1.0, 0.0]) * chord
    if len(p) > 1 and np.linalg.norm(p[1] - p[0]) > 1e-6:
        d = p[1] - p[0]
        t1 = d / np.linalg.norm(d) * chord
    else:
        t1 = p1 / max(chord, 1e-6) * chord
    u = np.linspace(0.0, 1.0, samples)[:, None]
    h00, h10, h01, h11 = 2 * u**3 - 3 * u**2 + 1, u**3 - 2 * u**2 + u, -2 * u**3 + 3 * u**2, u**3 - u**2
    bridge = h00 * p0 + h10 * t0 + h01 * p1 + h11 * t1
    return np.vstack([bridge[:-1], p])


def point_at_arclength(poly: np.ndarray, s: float) -> np.ndarray:
    seg = np.linalg.norm(np.diff(poly, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    if s >= cum[-1]:
        return poly[-1]
    return np.array([np.interp(s, cum, poly[:, 0]), np.interp(s, cum, poly[:, 1])])


def command_from_route_bridge(waypoints_xy: np.ndarray, s_m: float = S_LOOKAHEAD_M,
                              threshold_m: float = LATERAL_THRESHOLD_M) -> DriveCommand:
    p = np.asarray(waypoints_xy, np.float64).reshape(-1, 2)
    if len(p) == 0:
        return DriveCommand.UNKNOWN
    if p[0, 0] <= 0.5:                     # route starts beside or behind the car: no bridge, read it directly
        poly = np.vstack([np.zeros(2), p])
    else:
        poly = bridged_route(p)
    y = point_at_arclength(poly, s_m)[1]
    if y > threshold_m:
        return DriveCommand.LEFT
    if y < -threshold_m:
        return DriveCommand.RIGHT
    return DriveCommand.STRAIGHT


def bridge_one_hot(route) -> np.ndarray:
    """gRPC Route -> NAVSIM command one-hot."""
    xy = np.array([[w.x, w.y] for w in route.waypoints], np.float64).reshape(-1, 2)
    return command_one_hot(command_from_route_bridge(xy))


def snap_plan_to_route(plan: np.ndarray, waypoints_xy: np.ndarray, s0_m: float = 5.0, s1_m: float = 25.0) -> np.ndarray:
    """Route following for a model that ignores the command (WA-JEPA, measured 2026-10-02).

    Keeps the plan's progress (arc length s_i of each pose along the plan) and its own path near the
    car, and blends onto the bridged route further out: weight w = 0 up to s0, rising linearly to 1 at
    s1, then the pose sits on the route at the same arc length. Yaw follows the blended path.
    Unchanged if there is no route or the plan is (nearly) stationary.
    """
    plan = np.asarray(plan, np.float64)
    p = np.asarray(waypoints_xy, np.float64).reshape(-1, 2)
    xy = plan[:, :2]
    seg = np.linalg.norm(np.diff(np.vstack([np.zeros(2), xy]), axis=0), axis=1)
    s = np.cumsum(seg)
    if len(p) == 0 or s[-1] < 2.0:
        return plan.copy()
    poly = np.vstack([np.zeros(2), p]) if p[0, 0] <= 0.5 else bridged_route(p)
    q = np.stack([point_at_arclength(poly, si) for si in s])
    w = np.clip((s - s0_m) / max(s1_m - s0_m, 1e-6), 0.0, 1.0)[:, None]
    out_xy = (1.0 - w) * xy + w * q
    d = np.diff(np.vstack([np.zeros(2), out_xy]), axis=0)
    yaw = np.arctan2(d[:, 1], d[:, 0])
    moving = np.linalg.norm(d, axis=1) > 1e-3
    yaw = np.where(moving, yaw, plan[:, 2])
    return np.column_stack([out_xy, yaw])


def target_point_py123d(waypoints_xy: np.ndarray | None, distance_m: float = 45.0,
                        resolution_m: float = 0.1) -> np.ndarray | None:
    """The route target point exactly as py123d_garage's AlpaSim driver builds it (driver_service._plan @ v0.1.1):
    the route waypoints in the rig frame, the ego origin prepended when the first waypoint is farther than the
    route resolution, extended along the final heading to distance + 2 m, then the point `distance_m` along the arc.
    This is also how the WA-JEPA route pilot's training targets were made (py123d get_target_points on the log's
    route, measured from the ego's progress), so the policy sees the same signal in simulation."""
    if waypoints_xy is None:
        return None
    p = np.asarray(waypoints_xy, np.float64).reshape(-1, 2)
    p = p[~np.isnan(p).any(axis=1)]
    if len(p) == 0:
        return None
    if float(np.linalg.norm(p[0])) > resolution_m:
        p = np.vstack([np.zeros((1, 2)), p])
    if len(p) < 2:
        return None
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    short = distance_m + 2.0 - float(seg.sum())
    if short > 0:                                            # _extend_route: along the last metre's heading
        arc_from_end = np.concatenate([[0.0], np.cumsum(seg[::-1])])[::-1]
        tail = min(max(int(np.searchsorted(-arc_from_end, -1.0)) - 1, 0), len(p) - 2)
        h = p[-1] - p[tail]
        n = float(np.linalg.norm(h))
        if n > 0:
            p = np.vstack([p, p[-1] + h / n * short])
            seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    keep = np.concatenate([[True], seg > 0.0])
    p = p[keep]
    arc = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))])
    s = min(distance_m, float(arc[-1]))
    return np.array([np.interp(s, arc, p[:, 0]), np.interp(s, arc, p[:, 1])], np.float32)
