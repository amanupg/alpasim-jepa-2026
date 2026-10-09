# alpasim-jepa

**nuPlan track** of the **AlpaSim E2E Closed-Loop Challenge 2026**. The PAI track is the main line in
`../alpasim` (Alpamayo); this thread owns nuPlan.

**Rule (Aman, 2026-09-29):** `../alpasim`, `../jepa-nureasoning` and `../nureasoning` are
read-only from here. Everything borrowed is listed in [BORROWED.md](BORROWED.md).
Evidence, results and decisions live in [LEDGER.md](LEDGER.md).

## Status (2026-10-09)
- **Local score cannot rank model families.** NAVSIM-tuned models (WA-JEPA, LTF, GTRS) score high locally but low
  officially, so only same-model comparisons are trusted locally. The simulator is deterministic (reruns identical).
- **Base:** the public py123d checkpoint (kesai-labs, Apache-2.0): 0.848 official scene score (another team's entry).
- **Best py123d recipe:** GTRS-Dense judge (margin 3, radius 3 m) + a 1.10 time warp on near-straight plans, skipped
  when the judge substituted its path. **+0.113 [+0.080, +0.149]** over plain py123d on 193 never-used scenes
  (node-local parts 003 + 014); every step was confirmed on scenes not used to choose it (LEDGER.md).
- **WA-JEPA + judge (margin 1)** image built (planned tag `v4`); judge gain +0.025 on held-out scenes.
- **Training (Aman approved):** py123d nuPlan fine-tune and a route-conditioned WA-JEPA pilot (frozen encoder,
  trajectory stream + target-point encoder), both with all data on node-local disk (the dept fileset is full).
- Open: whether the NAVSIM-trained judge transfers to the official score; the October slot order is Aman's call.

## Layout
- `src/wajepa_challenge/`: WA-JEPA driver for the AlpaSim egodriver API, GTRS judge (`judge.py`, vendored
  `gtrs/`), route bridge, time warp.
- `src/garage_addons/`: py123d driver with our add-ons (judge, time warp), without modifying py123d.
- `src/wajepa_route/`: WA-JEPA route pilot (samples from nuPlan 123D, frozen-feature cache, training).
- `src/analysis/`: run comparison (`report.py`), route audit, log slimming.
- `cluster/`: Insomnia Slurm jobs (closed-loop nuPlan/PAI sims, data fetch, setup).
- `container/`: submission image recipes and notices.
