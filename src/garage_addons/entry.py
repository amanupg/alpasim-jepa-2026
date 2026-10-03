"""py123d_garage AlpaSim driver with our add-ons, without modifying its code.

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0, v0.1.1) after wrapping
`driver_service._make_plan`, the one function that receives each fresh rig-frame plan ([8, 2] at 0.5 s):
  GARAGE_TIME_SCALE in [1.0, 1.25]: the organisers' trajectory time warp (wajepa_challenge/timewarp.py,
  same rule as their GTRS sample), applied to the plan before it is anchored and cached.
  GARAGE_TS_MAX_TURN_DEG (default off): apply the warp only if the plan's heading change over its
  4 s is below this many degrees (straight roads); curves keep the original timing. At scale 1.10 the
  warp helped 72 scenes and hurt 16, the losses mostly offroad in curves (LEDGER 2026-10-03).
"""
from __future__ import annotations

import importlib.util
import logging
import os
import pathlib

import numpy as np

_TW = pathlib.Path(__file__).resolve().parent.parent / "wajepa_challenge" / "timewarp.py"
_spec = importlib.util.spec_from_file_location("_timewarp", _TW)      # no WA-JEPA package import
timewarp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(timewarp)

from py123d_garage.evaluation.alpasim import evaluate                    # noqa: E402
from py123d_garage.evaluation.alpasim.help import driver_service        # noqa: E402

LOG = logging.getLogger("garage_addons")
TIME_SCALE = float(os.environ.get("GARAGE_TIME_SCALE", "1.0"))
MAX_TURN_DEG = float(os.environ.get("GARAGE_TS_MAX_TURN_DEG", "inf"))


def _heading_change_deg(xy: np.ndarray) -> float:
    d = np.diff(np.vstack([np.zeros(2), xy]), axis=0)
    moving = np.linalg.norm(d, axis=1) > 0.2
    if moving.sum() < 2:
        return 0.0
    h = np.unwrap(np.arctan2(d[moving, 1], d[moving, 0]))
    return float(np.degrees(np.abs(h - h[0]).max()))

_make_plan = driver_service._make_plan


def _make_plan_with_addons(positions_rig, ego_pose_local, time_now_us, interval_us):
    xy = np.asarray(positions_rig, np.float64)
    if (TIME_SCALE != 1.0 and interval_us == 500_000 and xy.shape[0] == 8
            and _heading_change_deg(xy) < MAX_TURN_DEG):
        plan = np.column_stack([xy, np.zeros(len(xy))])
        xy = timewarp.warp_plan(plan, TIME_SCALE)[:, :2]
    return _make_plan(xy, ego_pose_local, time_now_us, interval_us)


driver_service._make_plan = _make_plan_with_addons

if __name__ == "__main__":
    LOG.warning("garage add-ons: time scale %s (only below %s deg heading change)", TIME_SCALE, MAX_TURN_DEG)
    evaluate.main()
