# alpasim-jepa

**nuPlan track** of the **AlpaSim E2E Closed-Loop Challenge 2026**. The PAI track is the main line in
`../alpasim` (Alpamayo); this thread owns nuPlan.

**Rule (Aman, 2026-09-29):** `../alpasim`, `../jepa-nureasoning` and `../nureasoning` are
read-only from here. Everything borrowed is listed in [BORROWED.md](BORROWED.md).
Evidence, results and decisions live in [LEDGER.md](LEDGER.md).

## Status (2026-10-14)
- **Local score cannot rank model families.** NAVSIM-tuned models (WA-JEPA, LTF, GTRS) score high locally but low
  officially, so only same-model comparisons are trusted locally. The simulator is deterministic (reruns identical).
- **Base:** the public py123d checkpoint (kesai-labs, Apache-2.0): 0.848 official scene score (another team's entry).
- **Lead candidate Q** (`container/Dockerfile.q`, planned tag `v6`): our nuPlan fine-tune of py123d (epoch 15) +
  GTRS-Dense judge (margin 3, radius 3 m) + a 1.10 time warp on near-straight plans (skipped when the judge
  substituted its path) + the judge's stall rescue (3 m, margin 1). Paired gains, each confirmed on scenes not used
  to choose it (LEDGER.md): fine-tune + recipe +0.114 over plain py123d on 193 fresh scenes; stall rescue a further
  **+0.030 [+0.020, +0.039]** on 754 tuning / held-out / fresh scenes at 1 m (W35 / L4), and 3 m a further
  **+0.013 [+0.008, +0.019]** over 1 m (W31 / L2).
- **WA-JEPA + judge (margin 1)** image built (planned tag `v4`); judge gain +0.025 on held-out scenes. The
  route-conditioned WA-JEPA pilot was negative twice and is paused.
- Open: whether the NAVSIM-trained judge transfers to the official score.

## Layout
- `src/wajepa_challenge/`: WA-JEPA driver for the AlpaSim egodriver API, GTRS judge (`judge.py`, vendored
  `gtrs/`), route bridge, time warp.
- `src/garage_addons/`: py123d driver with our add-ons (judge, time warp), without modifying py123d.
- `src/wajepa_route/`: WA-JEPA route pilot (samples from nuPlan 123D, frozen-feature cache, training).
- `src/analysis/`: run comparison (`report.py`), route audit, log slimming.
- `cluster/`: Insomnia Slurm jobs (closed-loop nuPlan/PAI sims, data fetch, setup).
- `container/`: submission image recipes and notices.
