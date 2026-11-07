"""Candidate add-on on top of the v8 driver module (src/g2_addons/entry.py, which stays byte-identical to the image).

G2_TIME_SCALE in [1.0, 1.25] (default 1.0 = off): the organisers' trajectory time warp (the GTRS sample's
`_warped_source_times`, NVlabs/alpasim e2e_challenge, Apache-2.0; our 8-point port is src/wajepa_challenge/timewarp.py):
the plan's first 4 s are read ahead (t <= 1 s at scale * t, 1-3 s at t + (scale - 1), the lead tapering to 0 at 4 s),
so the MPC keeps up with it; poses after 4 s are unchanged. Applied after start-now (G2_START_K, as in v8), only to
plans whose heading changes less than G2_TS_MAX_TURN_DEG (default 10) over the first 4 s: on bends it cut corners
(LEDGER 2026-10-13, public py123d v0.1: 1.10 on all plans -0.014, straight-only +0.009).
Run with G2_MODULE=g2_cand.entry; MPC settings such as idx_start_penalty are wizard overrides, not set here.
"""
from __future__ import annotations

import logging
import os

import numpy as np

from g2_addons import entry as base
from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service

LOG = logging.getLogger("g2_cand")
TIME_SCALE = float(os.environ.get("G2_TIME_SCALE", "1.0"))
TS_MAX_TURN_DEG = float(os.environ.get("G2_TS_MAX_TURN_DEG", "10"))
WARP_HORIZON_S = 4.0
DT_S = base.DT_S
if not 1.0 <= TIME_SCALE <= 1.25:
    raise ValueError("G2_TIME_SCALE must be in [1.0, 1.25]")


def warped_source_times(t: np.ndarray, scale: float) -> np.ndarray:
    """The organisers' warp on [0, 4] s; identity after 4 s."""
    lead = scale - 1.0
    src = np.where(t <= 1.0, scale * t, np.where(t <= 3.0, t + lead, t + lead * (WARP_HORIZON_S - t)))
    return np.where(t <= WARP_HORIZON_S, np.clip(src, 0.0, WARP_HORIZON_S), t)


def heading_change_deg(poses: np.ndarray, horizon_s: float = WARP_HORIZON_S) -> float:
    xy = poses[: int(round(horizon_s / DT_S)), :2]
    d = np.diff(np.vstack([np.zeros(2), xy]), axis=0)
    moving = np.linalg.norm(d, axis=1) > 0.02                 # 0.2 m/s at 0.1 s steps
    if moving.sum() < 2:
        return 0.0
    h = np.unwrap(np.arctan2(d[moving, 1], d[moving, 0]))
    return float(np.degrees(np.abs(h - h[0]).max()))


def warp_poses(poses: np.ndarray, scale: float) -> np.ndarray:
    """[64, 3] rig-frame poses at 0.1 ... 6.4 s, read at the warped times (origin at t = 0)."""
    times = np.arange(len(poses) + 1) * DT_S
    src = np.vstack([np.zeros(3), np.asarray(poses, np.float64)])
    src[:, 2] = np.unwrap(src[:, 2])
    st = warped_source_times(times[1:], scale)
    return np.stack([np.interp(st, times, src[:, k]) for k in range(3)], 1)


def install() -> None:
    base.install()                                              # start-now exactly as in v8
    planned = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        poses = planned(self, policy, session, session_uuid)
        if TIME_SCALE == 1.0 or poses.shape != (64, 3) or heading_change_deg(poses) >= TS_MAX_TURN_DEG:
            return poses
        session._g2_warped = getattr(session, "_g2_warped", 0) + 1
        if session._g2_warped == 1:
            LOG.info("time warp %s: first warped plan (scale %.2f)", session_uuid, TIME_SCALE)
        return warp_poses(poses, TIME_SCALE)

    driver_service.GarageDriver._plan = _plan


if __name__ == "__main__":
    LOG.warning("g2 cand: start-now K=%d, time scale %.2f (heading change < %.0f deg)",
                base.START_K, TIME_SCALE, TS_MAX_TURN_DEG)
    install()
    evaluate.main()
