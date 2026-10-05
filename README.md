# alpasim-jepa

**nuPlan track** of the **AlpaSim E2E Closed-Loop Challenge 2026**. The PAI track is the main line in
`../alpasim` (Alpamayo); this thread owns nuPlan.

**Rule (Aman, 2026-09-29):** `../alpasim`, `../jepa-nureasoning` and `../nureasoning` are
read-only from here. Everything borrowed is listed in [BORROWED.md](BORROWED.md).
Evidence, results and decisions live in [LEDGER.md](LEDGER.md).

## Status (2026-10-05)
- **Local score cannot rank model families.** NAVSIM-tuned models (WA-JEPA, LTF, GTRS) score high locally
  but low officially, so only same-model comparisons are trusted locally.
- **Base:** the public py123d checkpoint (kesai-labs, Apache-2.0): 0.848 official scene score (another team's entry).
- **Best add-on for py123d:** the GTRS-Dense judge (margin 3) + a 1.10 time warp on near-straight plans,
  skipped when the judge substituted its path. **+0.032** on 300 tuning scenes, **+0.049** on 100 held-out
  scenes (shard 013). The simulator is deterministic (base reruns are identical), so these are add-on effects.
- **WA-JEPA + GTRS judge** image verified (planned tag `v4`); its official number will show whether the
  judge transfers to the official score.
- Open: whether the NAVSIM-trained judge helps officially; the October slot order is Aman's call.

## Layout
- `src/wajepa_challenge/`: WA-JEPA driver for the AlpaSim egodriver API, GTRS judge (`judge.py`, vendored
  `gtrs/`), route bridge, time warp.
- `src/garage_addons/`: py123d driver with our add-ons (judge, time warp), without modifying py123d.
- `src/analysis/`: run comparison, route audit, log slimming.
- `cluster/`: Insomnia Slurm jobs (closed-loop nuPlan/PAI sims, data fetch, setup).
- `container/`: submission image recipes and notices.
