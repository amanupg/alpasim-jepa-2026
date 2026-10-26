"""py123d_garage v0.2.2 AlpaSim driver with a start-from-rest add-on, without modifying its code.

Runs `py123d_garage.evaluation.alpasim.evaluate` (kesai-labs, Apache-2.0) after wrapping
`GarageDriver._plan`, which returns each fresh rig-frame plan (64 poses at 0.1 s).

The stall it fixes (LEDGER 2026-10-26): from rest, the released joint64 plans "wait ~2 s, then go" at every replan.
The MPC only tracks the next 2.5 s, which is all waiting, so the ego never starts while the logged car drives off.
G2_START_K >= 0 turns the add-on on: once the ego is stopped (speed < G2_START_V m/s) and the last K plans were
already wait-then-go (motion starts after >= G2_START_WAIT_S and the plan ends >= G2_START_D m away), the waiting
prefix of the next such plan is dropped, so its motion starts now; the tail is extended at constant velocity to keep
64 poses. A plan that stays stopped is never touched, so stops the policy commits to are kept. Off by default.
"""
from __future__ import annotations

import logging
import os

import numpy as np

from py123d_garage.evaluation.alpasim import evaluate
from py123d_garage.evaluation.alpasim.help import driver_service

LOG = logging.getLogger("g2_addons")
START_K = int(os.environ.get("G2_START_K", "-1"))            # -1 = off
START_V = float(os.environ.get("G2_START_V", "0.5"))         # ego counts as stopped below this speed
START_D = float(os.environ.get("G2_START_D", "3.0"))         # the plan must end at least this far away
START_WAIT_S = float(os.environ.get("G2_START_WAIT_S", "0.5"))
MOVE_M = 0.3                                                 # displacement that counts as having started
DT_S = 0.1


def start_now(poses: np.ndarray) -> tuple[np.ndarray, float] | None:
    """The plan with its waiting prefix dropped and the wait in seconds, or None if it is not wait-then-go."""
    disp = np.hypot(poses[:, 0], poses[:, 1])
    if disp[-1] < START_D or disp[0] > MOVE_M:
        return None
    first = int(np.argmax(disp > MOVE_M))                    # first pose past MOVE_M (index 0 is at 0.1 s)
    shift = first - 1                                        # keep the last still pose as the new first one
    if shift * DT_S < START_WAIT_S:
        return None
    kept = poses[shift:]
    step = kept[-1] - kept[-2]
    tail = kept[-1] + step * np.arange(1, shift + 1)[:, None]
    return np.vstack([kept, tail]), shift * DT_S


def install() -> None:
    original = driver_service.GarageDriver._plan

    def _plan(self, policy, session, session_uuid):
        poses = original(self, policy, session, session_uuid)
        if START_K < 0 or poses.shape != (64, 3):
            return poses
        waited = getattr(session, "_g2_wait_then_go", 0)
        shifted = start_now(poses) if session.speed_mps < START_V else None
        session._g2_wait_then_go = waited + 1 if shifted is not None else 0
        if shifted is None or waited < START_K:
            return poses
        LOG.info("start-now %s: dropped %.1f s of waiting after %d wait-then-go plans", session_uuid, shifted[1], waited)
        return shifted[0]

    driver_service.GarageDriver._plan = _plan


if __name__ == "__main__":
    LOG.warning("g2 add-ons: start-now K=%d (v < %.2f m/s, plan end >= %.1f m, wait >= %.1f s)",
                START_K, START_V, START_D, START_WAIT_S)
    install()
    evaluate.main()
