AlpaSim E2E Challenge 2026, nuPlan track submission (team amanupg)
Copyright 2026 team amanupg (AlpaSim E2E Challenge 2026)

This submission is made available under the Apache License, Version 2.0 (see /opt/LICENSE),
as required by the challenge terms (official-2026-08, section 5).

Third-party components incorporated in this image (all compatible with Apache-2.0):

1. py123d_garage driver and model code (/opt/py123d-garage, installed into /opt/venv)
   kesai-labs/py123d_garage v0.1.1, commit 288d34c, https://github.com/kesai-labs/py123d_garage
   License: Apache-2.0 (/opt/py123d-garage/LICENSE)

2. Model checkpoint /opt/checkpoint/model.pth (+ config.yaml): our fine-tune (team amanupg) of
   Hugging Face kesai-labs/py123d_garage_pretrained_checkpoints, revision 5516edd, resnet34_v0.1.0/model_0014.pth
   (sha256 d536614c8157381adf68dcb70d3ba48a5e2a796fa2369dc3d7f902d66a5ffe43; Apache-2.0, trained by its authors on
   public nuPlan and Physical AI AV data), further trained with py123d_garage's own nuPlan posttraining recipe on
   nuPlan train/val logs in 123D format (Hugging Face dataset kesai-labs/nuplan; nuPlan terms of use). No test-split
   data was used. Fine-tuned weights released under Apache-2.0 as this submission.
   /opt/checkpoint/sensor_rig.yaml: resnet34_v0.1.0/sensor_rig_0.yaml from the same repository (Apache-2.0).

3. alpasim_grpc 0.54.0, NVlabs/alpasim src/grpc @ 2023534. Copyright (c) 2026 NVIDIA Corporation. Apache-2.0.

4. Trajectory time warp (/opt/addons/wajepa_challenge/timewarp.py), same rule as the organisers' GTRS sample
   (NVlabs/alpasim e2e_challenge @ 2023534, Apache-2.0, Copyright (c) 2026 NVIDIA Corporation).

5. GTRS-Dense judge code: /opt/addons/wajepa_challenge/gtrs (vendored, unmodified apart from merging policy.py
   loading helpers and preprocessing.py into io_utils.py), from NVlabs/alpasim
   e2e_challenge/sample_submission_simscale_navsim_gtrs_dense @ 2023534 (an inference adaptation of SimScale
   GTRS-Dense). Copyright (c) 2026 NVIDIA Corporation. License: Apache-2.0 (gtrs/LICENSE, NOTICE.md).

6. GTRS-Dense checkpoint /opt/assets/gtrs/gtrs_dense_resnet_sim_reward_navhard.ckpt: Hugging Face dataset
   OpenDriveLab/SimScale, SimScale_ckpts/GTRS_Dense,
   sha256 8dad0395332ccd844785cbfc7c9e24cb3f8d8dbf5cb9ca7f8f8dc75478fcf409. License: Apache-2.0.
   Trajectory vocabulary /opt/assets/gtrs/navsim_16384.npy from NVlabs/alpasim @ 2023534 (git-lfs),
   sha256 e8c29cfc25add59ae8b64769a4554c6518878726178c0bd889fc8518ebe1261d. License: Apache-2.0.

7. Base image nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04 (NVIDIA CUDA/cuDNN runtime under NVIDIA's
   redistribution terms; Ubuntu packages under their own licenses) and Python packages installed from PyPI
   per py123d_garage's pyproject.toml, each under its own permissive license (torch/torchvision BSD-3-Clause,
   numpy BSD, timm Apache-2.0, hydra-core MIT, omegaconf BSD, grpcio Apache-2.0, py123d Apache-2.0, ...).

Our own code (/opt/addons/garage_addons, /opt/addons/wajepa_challenge apart from gtrs/) is licensed under Apache-2.0.
