"""Offline evaluation of the two candidate fixes from shadow-mode logs (src/g2_shadow), without changing any plan.

For every run dir given: reads <run>/shadow/*.jsonl (one line per plan) and <run>/aggregate/results-summary.json
(per-scene outcome), then, for a grid of trigger settings, counts in how many scenes each trigger would fire, split by
the scene's outcome under the unchanged driver:
  fail_offroad / fail_collision / fail_corridor (score 0), stuck (< 2 m driven, score < 1), low (other score < 1),
  clean (score 1).
A trigger that fires in clean scenes is a scene the fix could break; firing in failing scenes is where it could help.

Fix 2 (off-road guard): fires on a plan if any planned pose within the first H seconds that lies inside the BEV grid
has a predicted drivable probability below P at its centre (or, with side=1, at either side sample).
Fix 1 (stall nudge): fires on a plan if the ego is slow (< V m/s), the plan waits (moves < W m in its first 2 s),
and the model sees nothing in the way: no box of any class within D m ahead along the route corridor (|lateral| <
C m), no moving (> 1 m/s) vehicle or two-wheeler crossing (heading off ours by > 30 deg) within R m, and no static
object (sign / barrier / cone / generic) within S m ahead and 8 m laterally.

Usage: python3 shadow_triggers.py RUN_DIR [RUN_DIR ...]
"""
from __future__ import annotations

import glob
import itertools
import json
import math
import os
import sys
from collections import Counter, defaultdict

import numpy as np

DT = 0.1


def outcomes(run: str) -> dict[str, str]:
    d = json.load(open(os.path.join(run, "aggregate", "results-summary.json")))
    out = {}
    for r in d["rollouts"]:
        if r["score"] is None:
            continue
        m = r.get("score_metrics") or {}
        g = lambda k: m.get(k) or 0
        drove = (r.get("metrics") or {}).get("dist_traveled_m") or 0
        if g("collision_at_fault") > 0:
            c = "fail_collision"
        elif g("offroad") > 0:
            c = "fail_offroad"
        elif g("left_corridor_laterally") > 0:
            c = "fail_corridor"
        elif r["score"] < 1 and drove < 2:
            c = "stuck"
        elif r["score"] < 1:
            c = "low"
        else:
            c = "clean"
        out[r["clipgt_id"]] = c
    return out


def load_plans(run: str) -> dict[str, list[dict]]:
    plans = defaultdict(list)
    for f in glob.glob(os.path.join(run, "shadow", "*.jsonl")):
        scene = os.path.basename(f).split("__")[0]
        with open(f) as fh:
            plans[scene].extend(json.loads(line) for line in fh)
    for v in plans.values():
        v.sort(key=lambda r: r["plan"])
    return plans


def corridor_lateral(route: np.ndarray, pts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Arc length along the route and lateral distance of each point (straight ahead if no route)."""
    if len(route) < 2:
        return pts[:, 0], np.abs(pts[:, 1])
    seg = np.diff(route, axis=0)
    seglen = np.hypot(seg[:, 0], seg[:, 1]) + 1e-9
    s0 = np.concatenate([[0.0], np.cumsum(seglen)])
    best_d = np.full(len(pts), np.inf)
    best_s = np.zeros(len(pts))
    for i in range(len(seg)):
        t = np.clip(((pts - route[i]) @ seg[i]) / seglen[i] ** 2, 0, 1)
        proj = route[i] + t[:, None] * seg[i]
        d = np.hypot(*(pts - proj).T)
        better = d < best_d
        best_d[better] = d[better]
        best_s[better] = s0[i] + t[better] * seglen[i]
    return best_s, best_d


def fix2_fires(plan: dict, H: float, P: float, side: bool) -> bool:
    drv = np.array(plan.get("drv") or [], dtype=float)
    if drv.size == 0:
        return False
    n = int(round(H / DT))
    d = drv[:n]
    vals = d if side else d[:, :1]
    vals = vals[~np.isnan(vals)]
    return bool(vals.size and vals.min() < P)


def fix1_fires(plan: dict, V: float, W: float, D: float, C: float, R: float, S: float) -> bool:
    if plan["speed"] >= V:
        return False
    poses = np.array(plan["poses"])
    if np.hypot(poses[19, 0], poses[19, 1]) >= W:    # pose 19 = 2.0 s
        return False
    boxes = np.array(plan["boxes"], dtype=float).reshape(-1, 8)
    route = np.array(plan["route"], dtype=float).reshape(-1, 2)
    if len(boxes):
        s, lat = corridor_lateral(route, boxes[:, :2])
        ahead = boxes[:, 0] > -1.0
        if np.any(ahead & (s < D) & (lat < C)):
            return False
        cls, spd, yaw = boxes[:, 6], boxes[:, 5], boxes[:, 4]
        crossing = np.isin(cls, (0, 2)) & (np.abs(spd) > 1.0) & (np.abs(np.sin(yaw)) > math.sin(math.radians(30)))
        if np.any(crossing & (np.hypot(boxes[:, 0], boxes[:, 1]) < R) & (boxes[:, 0] > -5)):
            return False
        static = (cls == 3) & (boxes[:, 0] > 0) & (boxes[:, 0] < S) & (np.abs(boxes[:, 1]) < 8)
        if np.any(static):
            return False
    return True


def report(name: str, fires: dict[str, bool], cls: dict[str, str]) -> None:
    tot, hit = Counter(), Counter()
    for k, c in cls.items():
        tot[c] += 1
        hit[c] += bool(fires.get(k))
    cols = ["fail_offroad", "fail_collision", "fail_corridor", "stuck", "low", "clean"]
    print(f"{name:42s} " + "  ".join(f"{c.split('_')[-1]} {hit[c]}/{tot[c]}" for c in cols))


def main(runs: list[str]) -> None:
    cls, plans = {}, {}
    for r in runs:
        cls.update(outcomes(r))
        plans.update(load_plans(r))
    cls = {k: v for k, v in cls.items() if k in plans}
    print(f"{len(cls)} scenes with shadow logs; outcomes: {dict(Counter(cls.values()))}")
    print("\nFix 2 (off-road guard): fires if a pose in the first H s has drivable prob < P")
    for H, P, side in itertools.product((1.0, 2.0, 3.0), (0.1, 0.2, 0.3, 0.5), (False, True)):
        fires = {k: any(fix2_fires(p, H, P, side) for p in plans[k]) for k in cls}
        report(f"H={H} P={P} side={int(side)}", fires, cls)
    print("\nFix 1 (stall nudge): slow, waiting plan, nothing in the way")
    for V, W, D, C, R, S in itertools.product((0.5,), (1.0,), (15.0, 25.0, 40.0), (2.0, 3.0), (30.0, 50.0), (0.0, 15.0)):
        fires = {k: any(fix1_fires(p, V, W, D, C, R, S) for p in plans[k]) for k in cls}
        report(f"D={D} C={C} R={R} S={S}", fires, cls)


if __name__ == "__main__":
    main(sys.argv[1:])
