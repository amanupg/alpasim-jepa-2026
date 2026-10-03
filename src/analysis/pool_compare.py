"""Pool results-summary.json across shards per config and compare paired against a baseline config.
Usage: pool_compare.py ROOT  (ROOT holds <run>/aggregate/results-summary.json); configs defined below."""
import glob, json, random, statistics as st, sys
ROOT = sys.argv[1]
CONFIGS = {
    "wajepa":             ["nuplan_wajepa_v1_12994594", "nuplan_wajepa_shard010_12994803", "nuplan_wajepa_s005_*"],
    "judge":              ["nuplan_wajepa_judge_r1m1_13062081", "nuplan_wajepa_judge_r1m1_s010_*", "nuplan_wajepa_judge_r1m1_s005_*"],
    "routefollow(no model)": ["nuplan_wajepa_routefollow_s001_*", "nuplan_wajepa_routefollow_s010_*", "nuplan_wajepa_routefollow_s005_*"],
    "judge+snap":         ["nuplan_wajepa_judge_snap_s001_*", "nuplan_wajepa_judge_snap_s010_*", "nuplan_wajepa_judge_snap_s005_*"],
    "judge+snap+ts125":   ["nuplan_wajepa_judge_snap_ts125_s001_*", "nuplan_wajepa_judge_snap_ts125_s010_*", "nuplan_wajepa_judge_snap_ts125_s005_*"],
    "wajepa+bridge+ts125": ["nuplan_wajepa_bridge_ts125_s001_*", "nuplan_wajepa_bridge_ts125_s010_*", "nuplan_wajepa_bridge_ts125_s005_*"],
    "judge+bridge+ts125": ["nuplan_wajepa_judge_bridge_ts125_s001_*", "nuplan_wajepa_judge_bridge_ts125_s010_*", "nuplan_wajepa_judge_bridge_ts125_s005_*"],
}
def load(pats):
    d = {}
    for p in pats:
        g = glob.glob(f"{ROOT}/{p}/aggregate/results-summary.json")
        if not g: return None
        for r in json.load(open(g[0]))["rollouts"]:
            m = r.get("score_metrics") or {}
            d[r["clipgt_id"]] = tuple(float(v or 0.0) for v in (
                r["score"], m.get("offroad"), m.get("left_corridor_laterally"), m.get("collision_at_fault"),
                m.get("progress_clipped_rel"), m.get("dist_to_gt_trajectory")))
    return d
R = {k: load(v) for k, v in CONFIGS.items()}
R = {k: v for k, v in R.items() if v}
keys = sorted(set.intersection(*[set(v) for v in R.values()]))
print("scenes", len(keys))
print(f"{'config':22s} score  offroad corridor collision progress dist_gt")
for k, d in R.items():
    cols = [st.mean(d[s][i] for s in keys) for i in range(6)]
    print(f"{k:22s} " + " ".join(f"{c:.3f}" for c in cols))
random.seed(0)
def boot(a, b):
    diffs = [R[a][s][0] - R[b][s][0] for s in keys]
    bs = sorted(st.mean(random.choices(diffs, k=len(diffs))) for _ in range(4000))
    return f"{st.mean(diffs):+.3f} [{bs[200]:+.3f}, {bs[3800]:+.3f}] W{sum(x > 0 for x in diffs)} L{sum(x < 0 for x in diffs)}"
for a, b in [("wajepa+bridge+ts125", "wajepa"), ("judge+bridge+ts125", "judge"), ("judge+snap", "judge"),
             ("judge+snap+ts125", "judge+snap"), ("judge+snap+ts125", "judge"), ("judge+snap+ts125", "wajepa")]:
    if a in R and b in R: print(f"{a} - {b}: {boot(a, b)}")
