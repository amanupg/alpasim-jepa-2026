"""Paired comparisons of every nuPlan config against its model's baseline, per shard and pooled.
Usage: report.py DIR   (DIR holds <run>/results-summary.json, fetched from runs/<run>/aggregate/).
Runs are found by name: nuplan_<driver>_<tag>_s<shard>_<jobid>. The simulator is deterministic, so a paired
difference is the config's effect on those scenes; the bootstrap interval covers which scenes were sampled."""
import glob, json, random, re, statistics as st, sys
from collections import defaultdict

TUNING = ("001", "010", "005")              # used for choosing settings
HELDOUT = ("013", "007", "011")             # used to pick margin 3 (013) and radius 2 (all three)
FRESH = ("003", "014")                       # node-local parts (LOCAL_PART), fresh scenes only; for R3 and later
# The first runs of each baseline predate the naming scheme.
LEGACY = {("garage", "base", "001"): "nuplan_garage_s001_13121307", ("garage", "base", "010"): "nuplan_garage_s010_13121308",
          ("garage", "base", "005"): "nuplan_garage_s005_13121309", ("wajepa", "base", "001"): "nuplan_wajepa_v1_12994594",
          ("wajepa", "base", "010"): "nuplan_wajepa_shard010_12994803", ("wajepa", "base", "005"): "nuplan_wajepa_s005_13062857",
          ("wajepa", "judge_r1m1", "001"): "nuplan_wajepa_judge_r1m1_13062081"}
NAME = re.compile(r"nuplan_(garage|wajepa)_(?:(.+)_)?s(\d{3})_(\d+)$")
SKIP_TAGS = {"rerun"}                       # determinism check, identical to base


def load(path):
    out = {}
    for r in json.load(open(path))["rollouts"]:
        m = r.get("score_metrics") or {}
        out[r["clipgt_id"]] = (float(r["score"]), float(m.get("offroad") or 0), float(m.get("collision_at_fault") or 0),
                               float(m.get("progress_clipped_rel") or 0))
    return out


def main(root):
    runs = {}                               # (driver, tag, shard) -> run dir (latest job id wins)
    for p in sorted(glob.glob(f"{root}/nuplan_*/results-summary.json")):
        run = p.split("/")[-2]
        m = NAME.match(run)
        if not m:
            continue
        driver, tag, shard, job = m.group(1), m.group(2) or "base", m.group(3), int(m.group(4))
        if tag in SKIP_TAGS:
            continue
        key = (driver, tag, shard)
        if key not in runs or job > int(runs[key].rsplit("_", 1)[1]):
            runs[key] = run
    for key, run in LEGACY.items():
        if glob.glob(f"{root}/{run}/results-summary.json"):
            runs.setdefault(key, run)
    data = {k: load(f"{root}/{v}/results-summary.json") for k, v in runs.items()}
    configs = defaultdict(dict)
    for (driver, tag, shard) in data:
        configs[(driver, tag)][shard] = data[(driver, tag, shard)]
    random.seed(0)
    for group, shards in (("TUNING", TUNING), ("HELD-OUT", HELDOUT), ("FRESH", FRESH)):
        print(f"\n== {group} shards {'/'.join(shards)}: diff vs the same model's baseline on the same scenes")
        for (driver, tag), per in sorted(configs.items()):
            if tag == "base":
                continue
            base = configs.get((driver, "base"), {})
            have = [s for s in shards if s in per and s in base]
            if not have:
                continue
            d, a_all, b_all, per_shard = [], [], [], []
            for s in have:
                a, b = per[s], base[s]
                k = sorted(set(a) & set(b))
                dd = [a[x][0] - b[x][0] for x in k]
                d += dd; a_all += [a[x] for x in k]; b_all += [b[x] for x in k]
                per_shard.append(f"{s}:{st.mean(dd):+.3f}")
            bs = sorted(st.mean(random.choices(d, k=len(d))) for _ in range(4000))
            col = lambda xs, i: st.mean(x[i] for x in xs)
            print(f"{driver:6s} {tag:22s} n={len(d):3d} {col(a_all, 0):.3f} vs {col(b_all, 0):.3f} {st.mean(d):+.3f} "
                  f"[90% {bs[200]:+.3f}, {bs[3800]:+.3f}] W{sum(x > 0 for x in d)} L{sum(x < 0 for x in d)} "
                  f"bigW{sum(x > 0.5 for x in d)} bigL{sum(x < -0.5 for x in d)} offroad {col(a_all, 1):.3f}/{col(b_all, 1):.3f} "
                  f"coll {col(a_all, 2):.3f}/{col(b_all, 2):.3f} {' '.join(per_shard)}"
                  + ("" if len(have) == len(shards) else "  (partial)"))


if __name__ == "__main__":
    main(sys.argv[1])
