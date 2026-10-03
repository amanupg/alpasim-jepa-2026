"""py123d_garage AlpaSim driver with our add-ons, without modifying its code.

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0, v0.1.1) after wrapping
`driver_service._make_plan`, the one function that receives each fresh rig-frame plan ([8, 2] at 0.5 s):
  GARAGE_TIME_SCALE in [1.0, 1.25]: the organisers' trajectory time warp (wajepa_challenge/timewarp.py,
  same rule as their GTRS sample), applied to the plan before it is anchored and cached.
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

_make_plan = driver_service._make_plan


def _make_plan_with_addons(positions_rig, ego_pose_local, time_now_us, interval_us):
    xy = np.asarray(positions_rig, np.float64)
    if TIME_SCALE != 1.0 and xy.shape[0] >= 2 and interval_us == 500_000 and xy.shape[0] == 8:
        plan = np.column_stack([xy, np.zeros(len(xy))])
        xy = timewarp.warp_plan(plan, TIME_SCALE)[:, :2]
    return _make_plan(xy, ego_pose_local, time_now_us, interval_us)


driver_service._make_plan = _make_plan_with_addons

if __name__ == "__main__":
    LOG.warning("garage add-ons: time scale %s", TIME_SCALE)
    evaluate.main()
