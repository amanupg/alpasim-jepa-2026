"""Recovery labels for closed-loop records (src/g2_addons/collect.py), in py123d_garage's label format.

For a record taken at anchor time t with the ego at pose (x, y, yaw) in the rollout's local frame, and the session's
logged ego trajectory (the "expert"):
  1. project the ego onto the logged path near t: arc length s0, signed lateral offset e (left +), heading error dpsi;
  2. pick t*, the logged time at s0 closest to t (a log that waited at s0 keeps waiting only as long as it did then);
  3. trajectory label = logged poses at t* + 0.1 ... 6.4 s, each shifted by e * w(d) along the path's left normal and
     turned by dpsi * w(d), where d is the distance travelled past s0 and w falls smoothly from 1 to 0 over D =
     max(D_MIN, T_REC * speed): the car eases back onto the log instead of jumping to it;
  4. path label = 64 points at 1 m along the same eased path (route heading);
  5. both in the ego's anchor frame (x forward, y left), as build_trajectory_label / build_path_label return them.
The logged trajectory is extrapolated straight at its final speed past its end; records whose label needs more than
MAX_EXTRAP_S of extrapolation, or with |e| > MAX_OFFSET_M, are skipped. Actions are fitted at training time with
py123d's own fit_actions.
"""
from __future__ import annotations

import math

import numpy as np

STEP_S = 0.1
NUM_STEPS = 64
PATH_POINTS = 64
PATH_SPACING_M = 1.0
T_REC = 2.0
D_MIN = 8.0
MAX_OFFSET_M = 3.0
MAX_EXTRAP_S = 3.4         # at least 3 s of the 6.4 s label comes from the log
SEARCH_BACK_S, SEARCH_AHEAD_S = 4.0, 8.0
EXTRAP_SLACK_M = 5.0       # timing="own": straight extension past the log's end allowed beyond round 1's budget
STILL_STEP_M = 0.01        # a 0.1 s step under 1 cm (0.1 m/s) is jitter while stopped
PERTURB_RAMP_S = 1.5       # collect.py's RAMP_S


def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi


def _smooth_weight(d, span):
    u = np.clip(d / span, 0.0, 1.0)
    return 1.0 - u * u * (3.0 - 2.0 * u)


class LoggedPath:
    """The logged trajectory as a time- and arc-length-indexed path, extended straight past both ends."""

    def __init__(self, timestamps_us, xy, yaw):
        order = np.argsort(timestamps_us)
        self.t = np.asarray(timestamps_us, np.float64)[order] * 1e-6
        self.xy = np.asarray(xy, np.float64)[order]
        self.yaw = np.unwrap(np.asarray(yaw, np.float64)[order])
        seg = np.linalg.norm(np.diff(self.xy, axis=0), axis=1)
        self.s = np.concatenate([[0.0], np.cumsum(seg)])
        tail = max(1, min(len(self.t) - 1, 5))
        self.v_end = (self.s[-1] - self.s[-1 - tail]) / max(self.t[-1] - self.t[-1 - tail], 1e-6)

    def at_time(self, t):
        """(xy, yaw, s) at times t, straight at the final speed past the end."""
        t = np.asarray(t, np.float64)
        inside = np.clip(t, self.t[0], self.t[-1])
        xy = np.stack([np.interp(inside, self.t, self.xy[:, 0]), np.interp(inside, self.t, self.xy[:, 1])], -1)
        yaw = np.interp(inside, self.t, self.yaw)
        s = np.interp(inside, self.t, self.s)
        extra = np.maximum(t - self.t[-1], 0.0) * self.v_end
        heading = np.stack([np.cos(self.yaw[-1]), np.sin(self.yaw[-1])])
        return xy + extra[:, None] * heading, yaw, s + extra

    def at_arc(self, s):
        """(xy, heading) at arc lengths s, straight past the end; heading follows the path, not the logged yaw."""
        s = np.asarray(s, np.float64)
        keep = np.concatenate([[True], np.diff(self.s) > 1e-3])           # drop standstill duplicates
        ss, pts = self.s[keep], self.xy[keep]
        if len(ss) < 2:
            heading = np.full_like(s, self.yaw[-1])
            return self.xy[-1] + (s - self.s[-1])[:, None] * [math.cos(self.yaw[-1]), math.sin(self.yaw[-1])], heading
        seg_heading = np.unwrap(np.arctan2(np.diff(pts[:, 1]), np.diff(pts[:, 0])))
        inside = np.clip(s, ss[0], ss[-1])
        xy = np.stack([np.interp(inside, ss, pts[:, 0]), np.interp(inside, ss, pts[:, 1])], -1)
        idx = np.clip(np.searchsorted(ss, inside, side="right") - 1, 0, len(seg_heading) - 1)
        heading = seg_heading[idx]
        extra = np.maximum(s - ss[-1], 0.0)
        return xy + extra[:, None] * np.stack([np.cos(seg_heading[-1]), np.sin(seg_heading[-1])]), heading


def project(path: LoggedPath, ego_xy, anchor_s):
    """Arc length, signed lateral offset (left +) and path heading of the ego's projection near anchor time."""
    window = (path.t >= anchor_s - SEARCH_BACK_S) & (path.t <= anchor_s + SEARCH_AHEAD_S)
    idx = np.flatnonzero(window[:-1] & (np.linalg.norm(np.diff(path.xy, axis=0), axis=1) > 1e-3))
    if len(idx) == 0:
        return None
    a, b = path.xy[idx], path.xy[idx + 1]
    ab = b - a
    u = np.clip(np.einsum("ij,ij->i", ego_xy - a, ab) / np.einsum("ij,ij->i", ab, ab), 0.0, 1.0)
    foot = a + u[:, None] * ab
    k = int(np.argmin(np.linalg.norm(ego_xy - foot, axis=1)))
    i = idx[k]
    heading = math.atan2(ab[k, 1], ab[k, 0])
    rel = ego_xy - foot[k]
    lateral = -math.sin(heading) * rel[0] + math.cos(heading) * rel[1]
    return path.s[i] + u[k] * np.linalg.norm(ab[k]), lateral, heading


def time_at_arc(path: LoggedPath, s0, anchor_s):
    """The logged time at arc length s0 closest to the anchor time (standstills give an interval)."""
    near = np.flatnonzero(np.abs(path.s - s0) < 0.05)
    if len(near):
        return float(path.t[near[np.argmin(np.abs(path.t[near] - anchor_s))]])
    return float(np.interp(s0, path.s, path.t))


def recovery_labels(record: dict, gt: dict, timing: str = "log"):
    """(trajectory [64, 3], path [64, 3], info) in the ego anchor frame, or None when the record is unusable.

    timing="log": the trajectory follows the log's timing from t* (round 1).
    timing="own" (lateral-only): the trajectory keeps the policy's own speed profile (distance along its served plan,
    own_arc) and places it on the eased logged path, so only the geometry is corrected; the path label is the same.
    Records are filtered exactly as with "log", plus the same extension budget in metres (MAX_EXTRAP_S at the log's final speed, + EXTRAP_SLACK_M)."""
    path = LoggedPath(gt["timestamps_us"], gt["xy"], gt["yaw"])
    x, y, _, yaw = record["ego_pose_local"]
    anchor_s = record["anchor_us"] * 1e-6
    proj = project(path, np.array([x, y]), anchor_s)
    if proj is None:
        return None
    s0, lateral, path_heading = proj
    if abs(lateral) > MAX_OFFSET_M:
        return None
    dpsi = float(_wrap(yaw - path_heading))
    t_star = time_at_arc(path, s0, anchor_s)
    taus = np.arange(1, NUM_STEPS + 1) * STEP_S
    if t_star + taus[-1] - path.t[-1] > MAX_EXTRAP_S:
        return None
    future_xy, future_yaw, future_s = path.at_time(t_star + taus)
    v_ref = (future_s[19] - s0) / 2.0 if len(future_s) > 19 else 0.0
    span = max(D_MIN, T_REC * max(v_ref, record["speed_mps"]))

    def ease(xy, heading, s):
        w = _smooth_weight(np.maximum(s - s0, 0.0), span)
        _, path_dir = path.at_arc(np.maximum(s, 0.0))
        normal = np.stack([-np.sin(path_dir), np.cos(path_dir)], -1)
        return xy + (lateral * w)[:, None] * normal, heading + dpsi * w

    traj_xy, traj_yaw = ease(future_xy, future_yaw, future_s)
    path_s = s0 + np.arange(1, PATH_POINTS + 1) * PATH_SPACING_M
    path_xy, path_heading_pts = path.at_arc(path_s)
    path_xy, path_yaw = ease(path_xy, path_heading_pts, path_s)

    c, s = math.cos(yaw), math.sin(yaw)

    def to_anchor(xy, heading):
        rel = xy - [x, y]
        return np.stack([c * rel[:, 0] + s * rel[:, 1], -s * rel[:, 0] + c * rel[:, 1], _wrap(heading - yaw)], -1)

    info = {"s0": s0, "lateral": lateral, "dpsi": dpsi, "t_star": t_star, "anchor_s": anchor_s,
            "extrap_s": max(0.0, t_star + taus[-1] - path.t[-1])}
    if timing == "own":
        own = own_arc(record)
        if own[-1] - (path.s[-1] - s0) > MAX_EXTRAP_S * path.v_end + EXTRAP_SLACK_M:   # round 1's budget, in metres
            return None
        traj_s = s0 + own
        traj_xy, traj_yaw = ease(*path.at_arc(traj_s), traj_s)
        info["own_m"] = float(own[-1])
    return to_anchor(traj_xy, traj_yaw).astype(np.float32), to_anchor(path_xy, path_yaw).astype(np.float32), info


def own_arc(record) -> np.ndarray:
    """Distance travelled along the policy's own served plan at 0.1 ... 6.4 s, with collect.py's perturbation ramp
    removed and steps under STILL_STEP_M (sampling jitter while stopped) counted as 0."""
    poses = np.asarray(record["served_poses"], np.float64)[:, :2].copy()
    offset = record.get("perturb_m", 0.0)
    if offset:
        poses[:, 1] -= offset * np.clip(np.arange(1, NUM_STEPS + 1) * STEP_S / PERTURB_RAMP_S, 0.0, 1.0)
    steps = np.linalg.norm(np.diff(np.vstack([[0.0, 0.0], poses]), axis=0), axis=1)
    return np.cumsum(np.where(steps < STILL_STEP_M, 0.0, steps))
