# alpasim-jepa: nuPlan track, NVIDIA AlpaSim End-to-End Closed-Loop Challenge 2026

Team **amanupg** (Aman Upganlawar, Columbia University). Track **closed** 2026-11-16.

## Result
- **Final rank: 18th of 63 teams** on the nuPlan track leaderboard.
- Final entry **v10**: Policy Capability Score (PCS) **2450** [2303, 2597] on the final board (2320 at submission,
  2026-11-15); 1,000 / 1,000 closed-loop rollouts valid, 1,195 s of the 3,000 s compute budget.
- **Technical report accepted** (2026-11-16):
  [Local Gains That Did Not Transfer: Closed-Loop Lessons From Adapting a Released Latent TransFuser](report/amanupg_nuplan_report_final.pdf).

## What the project is
AlpaSim is NVIDIA's closed-loop driving simulator. Each entry is a Docker image that drives ~1,000 private nuPlan
scenes from 8 camera feeds, scored by an item-response-theory metric (PCS). This repo is the full nuPlan-track
campaign (Sep 29 to Nov 16, 2026): drivers, add-ons, training code, Slurm pipelines, submission recipes, analysis
and a day-by-day research ledger.

The final entry is the released py123d_garage v0.2.0 Latent TransFuser (waypoints head, seed 1) run unmodified,
because nothing we built beat it under a test we trusted. The main finding, written up in the report: three changes
that improved local nuPlan scores with confidence intervals above zero (+0.012 to +0.128 mean scene score on up to
754 paired scenes, including held-out ones) all lost on the private board. A second local simulator (NVIDIA NuRec
reconstructions, longer scenes) predicted the board's direction in 3 of 3 cases where local nuPlan predicted 0 of 3.

## What was tried (all measured, most negative)
- WA-JEPA (V-JEPA 2.1 world-model planner, 788M params): driver, route-conditioned fine-tune pilots.
- GTRS-Dense learned critic with radius-limited, margin-gated plan substitution; time warp; stall rescue.
- Fine-tuning py123d Latent TransFuser on nuPlan (full, decoder-only, weight averaging, soups, seed ensembles).
- Diagnosis of a receding-horizon "wait, then go" failure and rule fixes (start-now, stall nudge).
- Shadow-mode logging of the model's own perception to design triggers offline; firing-set paired evaluation.
- Speed caps, controller gains, emergency brake (offline), route leash.
- On-policy distillation (DAgger) with a sampler-exact loss through the planner's served Euler integral.
- A local refit of the challenge's Drive-IRT metric, and its validity check against the board.

## Scale
541 GPU-hours on Columbia's Insomnia Slurm cluster (L40S, L40, H100, A6000, RTX PRO 6000 Blackwell), roughly
700 to 900 jobs, 1,400+ local nuPlan scenes plus 440 NuRec scenes, 5 official submissions.

## Layout
- `report/`: the accepted technical report (PDF + LaTeX) and an earlier draft.
- `LEDGER.md`: chronological record of every experiment, number and decision (the source of truth).
- `notes/`: summaries (final campaign record, Nov 15 summary, storage assessment).
- `src/wajepa_challenge/`: WA-JEPA driver for the AlpaSim egodriver API, GTRS judge (vendored `gtrs/`).
- `src/garage_addons/`, `src/g2_*`: add-ons that wrap the py123d_garage driver without modifying it
  (`g2_addons` start-now, `g2_nudge` stall nudge, `g2_shadow` perception logging, `g2_slow` speed caps,
  `g2_leash` route leash, `g2_dagger` on-policy distillation).
- `src/wajepa_route/`, `src/closed_loop/`: training code (WA-JEPA route pilot, closed-loop decoder fine-tuning).
- `src/analysis/`, `src/tools/`, `analysis/pool_scripts/`: paired comparisons, pooling, audits.
- `cluster/`: Slurm jobs (closed-loop nuPlan / NuRec / PAI simulation, data fetch, training).
- `container/`: submission Dockerfiles with LICENSE and per-image NOTICE files.
- `pai_flashdrive/`: an early PAI-track driver experiment (handed to the PAI thread).
- `tests/`: driver tests with simulated gRPC traffic.

## Credits and licences
Third-party code and models are credited in [BORROWED.md](BORROWED.md) and the NOTICE files: NVlabs/alpasim
samples (Apache-2.0), kesai-labs py123d_garage and checkpoints (Apache-2.0 at revision 56edbe90), WA-JEPA
(Apache-2.0), OpenDriveLab GTRS / SimScale (Apache-2.0), FlashDrive (MIT). No model weights or datasets are stored
in this repository. nuPlan data is CC BY-NC-SA 4.0 (Motional).
