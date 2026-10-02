"""Audit drive commands on logged AlpaSim rollouts: organisers' rule vs route bridge (NAVSIM s=20 m).
Run with the alpasim-base python (alpasim_utils). Usage: route_audit.py OUT.json RUN_DIR [RUN_DIR ...]"""
import asyncio, glob, json, os, sys
from collections import Counter
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from alpasim_utils.logs import async_read_pb_log
from wajepa_challenge.route_bridge import command_from_route_bridge

def organisers(xy):
    if len(xy) == 0: return "UNKNOWN"
    t = next((p for p in xy if np.hypot(*p) >= 5.0), None)
    if t is None: return "STRAIGHT"
    return "LEFT" if t[1] > 2 else "RIGHT" if t[1] < -2 else "STRAIGHT"

async def one(path):
    rows, kinds = [], Counter()
    async for e in async_read_pb_log(path):
        k = e.WhichOneof("log_entry"); kinds[k] += 1
        if k == "route_request":
            xy = np.array([[w.x, w.y] for w in e.route_request.route.waypoints]).reshape(-1, 2)
            rows.append({"org": organisers(xy), "bridge": command_from_route_bridge(xy).name,
                         "n": len(xy), "first": xy[0].round(1).tolist() if len(xy) else None})
    return rows, kinds

async def main():
    out = {}
    for run in sys.argv[2:]:
        for f in sorted(glob.glob(f"{run}/rollouts/*/*/rollout.asl")):
            scene = f.split("/rollouts/")[1].split("/")[0]
            rows, kinds = await one(f)
            out[scene] = rows
            if len(out) == 1: print("entry kinds:", dict(kinds))
    json.dump(out, open(sys.argv[1], "w"))
    pairs = Counter((r["org"], r["bridge"]) for v in out.values() for r in v)
    print("steps", sum(pairs.values()), "scenes", len(out)); print(pairs)
    print("first waypoint x range", np.percentile([r["first"][0] for v in out.values() for r in v if r["first"]], [5, 50, 95]).round(1))
asyncio.run(main())
