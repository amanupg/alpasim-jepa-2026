"""py123d_garage v0.2.2 AlpaSim driver with a moving-only slow-down (last-slot candidate, LEDGER 2026-11-13).

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0) after wrapping `GarageDriver._plan`.
When the ego already moves at >= G2_SLOW_VMIN m/s, the model's plan is retimed to G2_SLOW_F of its speed: the pose
served for time t is the model's pose for time F * t (same path, same stops, reached later). At lower speed (starts
from rest, creeping, stopping) the plan is left alone, so the stall-prone starts are not made worse.

Why: the board punished both add-ons that made the car more assertive (v8, v9); a scene scores full once progress
reaches 80 % of the logged distance, so ~10 % slower costs nothing on most scenes and may cut lateral drift (off-road
is W1's largest incident type). Untested direction so far (only speed-ups, warp 1.10/1.25, were tested).
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
# G2_SLOW_CURVE_DEG > 0: only when the plan turns by more than this many degrees within its first 3 s (off-road, W1's
# largest incident type, comes from drift in turns), so straight driving keeps its speed
CURVE = float(os.environ.get("G2_SLOW_CURVE_DEG", "0"))
DT = 0.1


def retime(poses: np.ndarray, f: float) -> np.ndarray:
    """Pose at time t of the returned plan = pose at time f * t of the input plan (poses at DT, 2 DT, ...; origin at
    t = 0). Heading interpolated on the unwrapped angle."""
    n = len(poses)
    t = DT * np.arange(0, n + 1)
    full = np.vstack([np.zeros((1, 3)), poses])
    yaw = np.unwrap(full[:, 2])
    q = f * t[1:]
    h = np.interp(q, t, yaw)
    h = (h + np.pi) % (2 * np.pi) - np.pi
    return np.column_stack([np.interp(q, t, full[:, 0]), np.interp(q, t, full[:, 1]), h])


def turns(poses: np.ndarray) -> float:
    """Largest absolute heading change (deg) of the plan within its first 3 s."""
    return float(np.degrees(np.max(np.abs(np.unwrap(np.concatenate([[0.0], poses[:30, 2]]))))))


def install() -> None:
    original = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        poses = original(self, policy, session, session_uuid)
        try:
            if poses.shape == (64, 3) and float(session.speed_mps) >= VMIN and F < 1.0:
                if CURVE <= 0 or turns(poses) > CURVE:
                    return retime(poses, F)
        except Exception:  # a failure here must fall back to the model's plan
            LOG.exception("slow-down failed for %s", session_uuid)
        return poses

    driver_service.GarageDriver._plan = _plan


if __name__ == "__main__":
    LOG.warning("g2 slow: F=%.2f vmin=%.1f curve_deg=%.0f", F, VMIN, CURVE)
    install()
    evaluate.main()
