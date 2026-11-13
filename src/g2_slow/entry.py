"""py123d_garage v0.2.2 AlpaSim driver with a speed cap below the model's own intended speed (last-slot candidate,
LEDGER 2026-11-13). Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0) after wrapping
`GarageDriver._plan`.

Cap: target = G2_SLOW_F x the model's planned speed over the last second of its 6.4 s plan (its cruise intent, which does
not depend much on the current speed). The served plan keeps the model's path and is never ahead of the model's own
timing; its speed is limited to the target, reached from the current speed at <= G2_SLOW_DEC m/s^2. Only when the ego
moves at >= G2_SLOW_VMIN m/s; starts from rest and the model's own stops are untouched (a slower plan is never changed).
G2_SLOW_CURVE_DEG > 0: only when the plan turns by more than that within its first 3 s.

v1 (11-12, retime every plan to F of its speed) compounded through the speed input: each plan started from an already
slowed ego, so the car crawled (NuRec chunk 0: distance 67 -> 16 m, -0.36). The cap is anchored to the model's intent,
not to the current speed, so it does not compound.
"""
from __future__ import annotations

import logging
import os

import numpy as np

from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service

LOG = logging.getLogger("g2_slow")
F = float(os.environ.get("G2_SLOW_F", "0.9"))
VMIN = float(os.environ.get("G2_SLOW_VMIN", "2.0"))
DEC = float(os.environ.get("G2_SLOW_DEC", "1.0"))
CURVE = float(os.environ.get("G2_SLOW_CURVE_DEG", "0"))
DT = 0.1


def turns(poses: np.ndarray) -> float:
    """Largest absolute heading change (deg) of the plan within its first 3 s."""
    return float(np.degrees(np.max(np.abs(np.unwrap(np.concatenate([[0.0], poses[:30, 2]]))))))


def capped(poses: np.ndarray, v0: float, f: float = F, dec: float = DEC) -> np.ndarray:
    """The plan along the same path, with speed <= max(f * intent, v0 - dec * t) and never ahead of the model."""
    full = np.vstack([np.zeros((1, 3)), poses])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(full[:, :2], axis=0).T))])
    n = len(poses)
    t = DT * np.arange(0, n + 1)
    intent = (s[-1] - s[-11]) / (10 * DT)
    vt = f * intent
    v = np.maximum(vt, v0 - dec * t) if v0 > vt else np.full_like(t, vt)
    s_cap = np.concatenate([[0.0], np.cumsum(0.5 * (v[1:] + v[:-1]) * DT)])
    s_new = np.minimum(s, s_cap)
    if np.allclose(s_new, s):
        return poses
    s_mono = np.maximum.accumulate(s + 1e-9 * np.arange(n + 1))   # strictly increasing for interpolation
    yaw = np.unwrap(full[:, 2])
    q = s_new[1:]
    h = np.interp(q, s_mono, yaw)
    h = (h + np.pi) % (2 * np.pi) - np.pi
    return np.column_stack([np.interp(q, s_mono, full[:, 0]), np.interp(q, s_mono, full[:, 1]), h])


def install() -> None:
    original = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        poses = original(self, policy, session, session_uuid)
        try:
            v0 = float(session.speed_mps)
            if poses.shape == (64, 3) and v0 >= VMIN and F < 1.0 and (CURVE <= 0 or turns(poses) > CURVE):
                return capped(poses, v0)
        except Exception:  # a failure here must fall back to the model's plan
            LOG.exception("speed cap failed for %s", session_uuid)
        return poses

    driver_service.GarageDriver._plan = _plan


if __name__ == "__main__":
    LOG.warning("g2 slow (cap): F=%.2f vmin=%.1f dec=%.1f curve_deg=%.0f", F, VMIN, DEC, CURVE)
    install()
    evaluate.main()
