# NOTICE

- `trajectory.py` is copied from NVlabs/alpasim, `e2e_challenge/sample_submission_vavam/vavam_challenge/trajectory.py` (branch `e2e_challenge`, commit 2023534), Apache-2.0, Copyright (c) 2026 NVIDIA Corporation. Only the module docstring was changed.
- `driver.py` follows the structure of the same sample's `driver.py` (Apache-2.0, NVIDIA). The multi-camera buffering, ego-history construction and Alpamayo policy wiring are ours.
- Camera slot indices and the ego-history convention follow `src/driver/src/alpasim_driver/models/alpamayo_base.py` (Apache-2.0, NVIDIA).
- The model is NVIDIA Alpamayo 1.5 (`nvidia/Alpamayo-1.5-10B`), used under its own license; the code is from `NVlabs/alpamayo1.5` (commit 36aeb4c).

## FlashDrive (alpasim-jepa addition, 2026-10-23)
`flash_policy.py` uses FlashDrive (z-lab, https://github.com/z-lab/flashdrive, MIT License, Copyright (c) Z Lab)
at runtime: its backbone patches, ParoQuant W4A8 modules, expert fusion, compiled primitives and `euler_with_cache`.
Weights: z-lab/Alpamayo-1.5-10B and z-lab/Alpamayo-1.5-10B-PARO (derived from NVIDIA Alpamayo 1.5; NVIDIA License,
non-commercial).
