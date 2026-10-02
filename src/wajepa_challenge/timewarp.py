"""Trajectory time scale (WAJEPA_TIME_SCALE in [1.0, 1.25]).

Same warp as the organisers' GTRS sample (`navsim_gtrs_dense_challenge/trajectory.py::_warped_source_times`,
NVlabs/alpasim e2e_challenge @ 2023534, Apache-2.0, Copyright (c) 2026 NVIDIA Corporation): the plan is
read ahead of time in the near term (t <= 1 s: at scale * t; 1-3 s: t + (scale - 1); after 3 s the lead
tapers to 0 at the 4 s horizon), so the controller is asked to keep up with the plan while the endpoint
is unchanged. Applied here to WA-JEPA's [8, 3] plan at 0.5 s.
"""
from __future__ import annotations

import math

import numpy as np

MODEL_HORIZON_S = 4.0


def warped_source_times(times_s: np.ndarray, scale: float) -> np.ndarray:
    if not math.isfinite(scale) or not 1.0 <= scale <= 1.25:
        raise ValueError("trajectory time scale must be finite and in [1.0, 1.25]")
    if scale == 1.0:
        return times_s
    lead = scale - 1.0
    src = np.where(times_s <= 1.0, scale * times_s,
                   np.where(times_s <= 3.0, times_s + lead, times_s + lead * (MODEL_HORIZON_S - times_s)))
    return np.clip(src, 0.0, MODEL_HORIZON_S)


def warp_plan(plan: np.ndarray, scale: float) -> np.ndarray:
    """[8, 3] (x, y, yaw) at t = 0.5..4.0 s -> same shape, read at the warped times (origin at t = 0)."""
    plan = np.asarray(plan, np.float64)
    if scale == 1.0:
        return plan.copy()
    times = np.arange(0, 9) * 0.5
    src = np.vstack([np.zeros(3), plan])
    src[:, 2] = np.unwrap(src[:, 2])
    st = warped_source_times(times, scale)[1:]
    return np.stack([np.interp(st, times, src[:, k]) for k in range(3)], 1)
