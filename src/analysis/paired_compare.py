"""Paired per-scene comparison of a candidate against a baseline on the same scenes.

Usage: python paired_compare.py --base RUN [RUN ...] --cand RUN [RUN ...]
Reads <run>/aggregate/results-summary.json. Prints the mean difference with a 95% bootstrap CI over scenes,
wins/losses, new zeros (0 in candidate, > 0 in baseline) and fixed zeros, per shard and pooled, and lists every scene
that changed with its baseline outcome class (src/analysis/shadow_triggers.outcomes).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from shadow_triggers import outcomes  # noqa: E402


def scores(run: str) -> dict[str, float]:
    d = json.load(open(os.path.join(run, "aggregate", "results-summary.json")))
    return {r["clipgt_id"]: float(r["score"]) for r in d["rollouts"] if r["score"] is not None}


def summary(name: str, b: dict, c: dict, rng) -> None:
    keys = sorted(set(b) & set(c))
    if not keys:
        print(f"{name}: no common scenes")
        return
    d = np.array([c[k] - b[k] for k in keys])
    boot = rng.choice(d, size=(10000, len(d))).mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    new0 = sum(c[k] == 0 and b[k] > 0 for k in keys)
    fix0 = sum(b[k] == 0 and c[k] > 0 for k in keys)
    print(f"{name:10s} n={len(keys):4d} base {np.mean([b[k] for k in keys]):.4f} cand {np.mean([c[k] for k in keys]):.4f} "
          f"diff {d.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] W{(d > 1e-9).sum()}/L{(d < -1e-9).sum()} new0 {new0} fixed0 {fix0}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", nargs="+", required=True)
    ap.add_argument("--cand", nargs="+", required=True)
    a = ap.parse_args()
    rng = np.random.default_rng(0)
    B, C, cls = {}, {}, {}
    for rb, rc in zip(a.base, a.cand):
        b, c = scores(rb), scores(rc)
        summary(os.path.basename(rc)[-14:], b, c, rng)
        B.update(b)
        C.update(c)
        cls.update(outcomes(rb))
    summary("POOLED", B, C, rng)
    print("\nchanged scenes (baseline class, base -> cand):")
    for k in sorted(set(B) & set(C), key=lambda k: C[k] - B[k]):
        if abs(C[k] - B[k]) > 1e-9:
            print(f"  {cls.get(k, '?'):14s} {B[k]:.3f} -> {C[k]:.3f}  {k}")


if __name__ == "__main__":
    main()
