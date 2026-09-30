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
