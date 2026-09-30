#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_setup
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 01:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/setup_samples_%j.out
# Reference drivers: the organisers' SimScale NAVSIM samples (LTF, DiffusionDrive, GTRS-Dense ResNet
# reward), run read-only from the AlpaSim upstream checkout. This job fetches their public checkpoints
# (OpenDriveLab/SimScale, sha256-checked as in each sample's prepare_assets.sh) and a timm 1.0.27 overlay.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; NR=/insomnia001/depts/edu/users/au2327/nureasoning
W=$B/weights/simscale; mkdir -p $W
get() {  # repo path, expected sha256
  local f=$W/$(basename $1)
  [ -s $f ] || curl -sSfL --retry 5 -o $f.part "https://huggingface.co/datasets/OpenDriveLab/SimScale/resolve/main/$1" && [ -s $f.part ] && mv $f.part $f
  echo "$2  $f" | sha256sum -c -
}
get SimScale_ckpts/LTF/ltf_sim_navtest.ckpt 9c1a17651bb2cd8e2edf006ea45634432c38554a8f44e0714f64d11ea31f2c69
get SimScale_ckpts/DiffusionDrive/diffusiondrive_sim_navhard.ckpt 8fdbdb3fdfa7b496e7d7a438efbb5c2022377e59cbfd7095270d89623c5d963f
get SimScale_ckpts/GTRS_Dense/gtrs_dense_resnet_sim_reward_navhard.ckpt 8dad0395332ccd844785cbfc7c9e24cb3f8d8dbf5cb9ca7f8f8dc75478fcf409
# a15env has no pip: install with uv into a --target overlay, for that interpreter
$HOME/.local/bin/uv pip install -q --python $NR/ext/a15env/bin/python --target $B/envs/overlay_samples --no-deps \
  timm==1.0.27 dataclasses-json==0.6.7 marshmallow typing-inspect mypy-extensions opencv-python-headless==4.9.0.80
PYTHONNOUSERSITE=1 PYTHONPATH=$B/envs/overlay_samples $NR/ext/a15env/bin/python -c "import timm, cv2, dataclasses_json; print('timm', timm.__version__, 'cv2', cv2.__version__)"
ls -la $W
