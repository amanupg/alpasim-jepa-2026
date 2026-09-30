# NOTICE

- `driver.py`, `batch_worker.py`, `navigation.py` and `trajectory.py` are copied from NVlabs/alpasim, `e2e_challenge/sample_submission_simscale_navsim_transfuser/navsim_transfuser_challenge/` (branch `e2e_challenge`, commit 2023534), Apache-2.0, Copyright (c) 2026 NVIDIA Corporation.
  - Only `driver.py` is modified: 4 cameras × 4-frame history, pose history, resize on arrival, WA-JEPA policy wiring, and counter and log names.
- `preprocessing.py` and `policy.py` are ours. They follow WA-JEPA's reference adapters (`eval/navsim_agent.py`, `close_loop/hugsim_planner.py`) from Afari-Intelligent-Drive WA-JEPA @ bec2966 (Apache-2.0).
- The model is WA-JEPA (arXiv 2608.20974), checkpoint `model_state_dict.pt` (HF card: apache-2.0), built on Meta V-JEPA 2.1 (MIT).
