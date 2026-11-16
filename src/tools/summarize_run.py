"""One-screen summary of a local AlpaSim run (aggregate/results-summary.json).

Scene score and pass criteria are the evaluator's own (results-summary.json
"score_criteria"); the official leaderboard's Policy Capability Score is an IRT fit over
many policies and cannot be reproduced from one run, so compare runs on the SAME scenes.
Usage: python3 summarize_run.py RUN_DIR [RUN_DIR ...]   (stdlib only)
"""
import json
import os
import sys


def summarize(run):
    p = os.path.join(run, "aggregate", "results-summary.json")
    if not os.path.isfile(p):
        return {"run": os.path.basename(run.rstrip("/")), "error": "no results-summary.json"}
    d = json.load(open(p))
    ro = d.get("rollouts", [])
    sm = [r.get("score_metrics") or {} for r in ro]

    def mean(k, rows=sm):
        v = [r[k] for r in rows if r.get(k) is not None]
        return sum(v) / len(v) if v else float("nan")
    tel = d.get("telemetry") or {}
    return {
        "run": os.path.basename(run.rstrip("/")), "n": len(ro),
        "passed": sum(1 for r in ro if r.get("passed")), "failed_rollouts": sum(1 for r in ro if r.get("status") == "fail" and r.get("failure_reason")),
        "score": sum(r.get("score") or 0.0 for r in ro) / max(len(ro), 1),
        "collision_at_fault": mean("collision_at_fault"), "offroad": mean("offroad"),
        "left_corridor": mean("left_corridor_laterally"), "progress": mean("progress_clipped_rel"),
        "dist_to_gt": mean("dist_to_gt_trajectory"),
        "drive_rpc_mean_s": tel.get("driver_drive_rpc_duration_mean_s"), "drive_calls": tel.get("driver_drive_rpc_duration_count"),
        "failures": sorted({(r.get("failure_reason") or "")[:120] for r in ro if r.get("failure_reason")}),
    }


if __name__ == "__main__":
    for run in sys.argv[1:]:
        s = summarize(run)
        if "error" in s:
            print(s); continue
        print("%(run)s  n=%(n)d passed=%(passed)d  mean scene score %(score).3f  at-fault collision %(collision_at_fault).2f"
              "  offroad %(offroad).2f  left corridor %(left_corridor).2f  progress %(progress).2f  dist-to-gt %(dist_to_gt).2f m" % s)
        print("   drive rpc: %s calls, mean %s s" % (s["drive_calls"], s["drive_rpc_mean_s"]))
        for f in s["failures"]:
            print("   failure:", f)
