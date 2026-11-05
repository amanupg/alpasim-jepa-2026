# Borrowed (read-only)

| What | From | Why |
|---|---|---|
| WA-JEPA code @ `bec2966` (2026-09-04, Apache-2.0) | `../jepa-nureasoning/ext/WA-JEPA` | model definition, checkpoint loader, reference adapters (`close_loop/hugsim_planner.py`, `eval/navsim_agent.py`) |
| WA-JEPA checkpoint (`model_state_dict.pt`, 1.5 GB; HF card license apache-2.0) | `../jepa-nureasoning/weights/wa-jepa/` | the planner under test |
| Drive-JEPA code @ `548bb82` + perception-free ViT-L agent checkpoint (3.5 GB; weights CC0) | `../jepa-nureasoning/ext/Drive-JEPA`, `../jepa-nureasoning/weights/drive-jepa/` | second candidate |
| NVIDIA NAVSIM sample submission (TransFuser; `driver.py`, `batch_worker.py`, `navigation.py`, `trajectory.py`, Apache-2.0) | `../alpasim/external/alpasim/e2e_challenge/sample_submission_simscale_navsim_transfuser` (upstream NVlabs/alpasim, branch e2e_challenge, commit 2023534) | the organisers' template for NAVSIM-style drivers on the nuPlan track |
| Local closed-loop test bench (Apptainer sandboxes, nuPlan scene data, `sim_local.sbatch`, `compare_runs.py`, `failure_taxonomy.py`) | `../alpasim` (cluster: `.../au2327/alpasim`) | paired comparison against Alpamayo v0.3 on the same 100 nuPlan scenes. Runs must write outside `../alpasim` |
| v0.3 baseline results (nuPlan 30- and 100-scene runs) | `../alpasim` runs | the comparison baseline |

Nothing in this folder may be written back to the sources above.

## Added 2026-09-29 (validation of the WA-JEPA closed-loop result)
- **AlpaSim v0.3 Alpamayo driver** (`alpasim/src/a15_driver`) and its weights in the nureasoning HF cache: executed read-only as the paired baseline (`sim_nuplan.sbatch DRIVER=a15`), with the v0.3 image's `A15_INFERENCE_INTERVAL_US=1000000`. Nothing written into either tree (`PYTHONDONTWRITEBYTECODE=1`; the driver's caches go to /tmp).
- **Organisers' SimScale sample drivers** (LTF, DiffusionDrive, GTRS-Dense ResNet reward) from the upstream checkout `alpasim/external/alpasim/e2e_challenge` @ 2023534: executed read-only as reference drivers. Their checkpoints were downloaded by us from the public `OpenDriveLab/SimScale` dataset into `alpasim-jepa/weights/simscale`, sha256-checked against each sample's `prepare_assets.sh`.
- **nuPlan-track data:** our own copy of trajdata cache, scene configs and asset shard 010 (public `OpenDriveLab/AlpasimChallenge2026_nuplan_track`) in `alpasim-jepa/data/nuplan_track`, for scenes outside AlpaSim's shard 001.
- **Container inputs** are fetched from the public sources (not copied from other folders): WA-JEPA @ bec2966 from GitHub, weights from HF @ 15c0770e, `alpasim_grpc` from NVlabs/alpasim @ 2023534.
- **Shared nuPlan track metadata (2026-10-18, Aman approved):** `data/nuplan_track/nuplan_test` and `data/nuplan_track/navtest/configs` are symlinks into `../alpasim/data/nuplan_track/` (byte-identical copies; ours deleted to save space). Read-only.
- **Technical report template (2026-10-21):** `report/neurips_2026.sty`, `report/README.md`, `report/LICENSE-CC-BY-4.0.md` are the organisers' AlpaSim report package (CC BY 4.0 style adaptation), copied from `../alpasim/report/`. The TikZ figure style follows the PAI report there.
- **PAI FlashDrive bet (Aman approved 2026-10-23):** `pai_flashdrive/a15_driver/` is a copy of `../alpasim/src/a15_driver` (v5 driver, git d048ae8) with `flash_policy.py` added and a 12-line switch in `driver.py` (`A15_FLASH=1`). FlashDrive itself is cloned from GitHub (MIT) into `ext/flashdrive`. Read-only use of `../alpasim/data/ft_capture` (captured driver inputs) and `../nureasoning` (Qwen processor files, alpamayo1.5 source), as v5 does.

## 2026-11-05: no longer borrowed from ../alpasim
The cluster copy of `../alpasim` was deleted after the PAI campaign closed (Aman approved). What this folder used from it was moved here (plain `mv`, verified: file counts, token sha256, identical smoke-sim scores) and is now part of this folder: `data/nuplan_track/{nuplan_test, navtest/configs, navtest/assets (shard 001)}`, `sandbox/alpasim-base`, `ext/alpasim_sim` (NVlabs/alpasim e2e_challenge @ 2023534), `.cache/hf/token` (mode 600), and copies of `src/tools/{summarize_run,compare_runs}.py` and `runs/scenes_shard001/scene_ids.txt`. The rows above that name `../alpasim` describe the history; nothing on the cluster reads `../alpasim` any more.
