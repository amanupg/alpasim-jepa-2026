"""Scenes where a candidate add-on could act, from shadow logs of the plain driver (src/g2_shadow).

Both add-ons read only the model's own outputs, so until they first act a scene drives as the plain driver; scenes
outside the firing set are the plain run by construction and only the firing set needs a candidate run.
  nudge   src/g2_nudge trigger (shadow_triggers.fix1_fires, the deployed settings); exact = a run of >= K firing plans,
          loose = any single firing plan (covers near-misses if the simulator does not repeat bit for bit).
  startnow v8 (src/g2_addons, G2_START_K=3): acts on a stopped (< 0.5 m/s) wait-then-go plan after K such plans in a
          row, i.e. a run of >= K+1; loose = a run of >= K-1.
Usage: python firing_sets.py --kind nudge|startnow [--k 3] --out-exact F --out-loose F RUN [RUN ...]
Prints counts by baseline outcome class (shadow_triggers.outcomes).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import shadow_triggers as T  # noqa: E402

DT, MOVE_M, START_D, START_WAIT_S, START_V = 0.1, 0.3, 3.0, 0.5, 0.5


def wait_then_go(poses: np.ndarray) -> bool:
    disp = np.hypot(poses[:, 0], poses[:, 1])
    if disp[-1] < START_D or disp[0] > MOVE_M:
        return False
    return (int(np.argmax(disp > MOVE_M)) - 1) * DT >= START_WAIT_S


def longest_run(flags: list[bool]) -> int:
    best = cur = 0
    for f in flags:
        cur = cur + 1 if f else 0
        best = max(best, cur)
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=("nudge", "startnow"), required=True)
    ap.add_argument("--k", type=int, default=3)
    ap.add_argument("--out-exact", required=True)
    ap.add_argument("--out-loose", required=True)
    ap.add_argument("runs", nargs="+")
    a = ap.parse_args()
    cls, plans = {}, {}
    for r in a.runs:
        cls.update(T.outcomes(r))
        plans.update(T.load_plans(r))
    runs = {}
    for sc, pl in plans.items():
        if a.kind == "nudge":
            flags = [T.fix1_fires(p, 0.5, 1.0, 25.0, 2.0, 30.0, 15.0) for p in pl]
        else:
            flags = [p["speed"] < START_V and wait_then_go(np.array(p["poses"])) for p in pl]
        runs[sc] = longest_run(flags)
    need_exact, need_loose = (a.k, 1) if a.kind == "nudge" else (a.k + 1, max(a.k - 1, 1))
    exact = sorted(s for s, n in runs.items() if n >= need_exact)
    loose = sorted(s for s, n in runs.items() if n >= need_loose)
    missing = sorted(set(cls) - set(plans))
    print(f"{len(plans)} scenes with logs ({len(missing)} scored scenes without logs); outcomes {dict(Counter(cls.values()))}")
    for name, S in (("exact", exact), ("loose", loose)):
        print(f"{a.kind} {name}: {len(S)} scenes {dict(Counter(cls.get(s, '?') for s in S))}")
    for f, S in ((a.out_exact, exact), (a.out_loose, loose)):
        with open(f, "w") as fh:
            fh.write("\n".join(S) + ("\n" if S else ""))


if __name__ == "__main__":
    main()
