"""Paired comparison of local AlpaSim runs on the same scenes (stdlib only).

For each variant run vs a baseline run: mean scene score, passes, and the per-scene paired
difference (wins / losses / ties) with a bootstrap 90% interval on the mean difference.
Scenes present in only one run are dropped and counted. The scene score is the evaluator's
own per-rollout score from aggregate/results-summary.json (failed rollouts score 0).
Usage: python3 compare_runs.py BASELINE_RUN VARIANT_RUN [VARIANT_RUN ...]
"""
import json
import os
import random
import sys


def scores(run):
    d = json.load(open(os.path.join(run, "aggregate", "results-summary.json")))
    out = {}
    for r in d.get("rollouts", []):
        out.setdefault(r["clipgt_id"], []).append(float(r.get("score") or 0.0))
    return {k: sum(v) / len(v) for k, v in out.items()}


def boot(diffs, n=5000, seed=0):
    rng = random.Random(seed)
    ms = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(n))
    return ms[int(0.05 * n)], ms[int(0.95 * n)]


def main():
    base_run, variants = sys.argv[1], sys.argv[2:]
    b = scores(base_run)
    name = lambda r: os.path.basename(r.rstrip("/"))
    print(f"baseline {name(base_run)}: n={len(b)} mean {sum(b.values()) / len(b):.3f} "
          f"passes {sum(1 for v in b.values() if v > 0)}")
    for vr in variants:
        try:
            v = scores(vr)
        except FileNotFoundError:
            print(f"{name(vr)}: no results"); continue
        common = sorted(set(b) & set(v))
        d = [v[k] - b[k] for k in common]
        lo, hi = boot(d) if d else (float("nan"), float("nan"))
        print(f"{name(vr)}: n={len(common)} (dropped {len(set(b) ^ set(v))}) mean {sum(v[k] for k in common) / len(common):.3f} "
              f"vs base {sum(b[k] for k in common) / len(common):.3f}  diff {sum(d) / len(d):+.3f} "
              f"[90% {lo:+.3f}, {hi:+.3f}]  wins {sum(x > 1e-9 for x in d)} losses {sum(x < -1e-9 for x in d)} "
              f"ties {sum(abs(x) <= 1e-9 for x in d)}")


if __name__ == "__main__":
    main()
