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
