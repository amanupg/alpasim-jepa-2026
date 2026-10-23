#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_v2fetch
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 01:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/py123d_v2_fetch_%j.out
# py123d_garage v0.2.0 checkpoints (released with v0.2.0, unchanged in v0.2.2; revision from the v0.2.2 release notes):
# ltf-base-joint64-68M (recommended) and ltf-streaming-joint64-68M, all stages + per-seed results. ~2 GB.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; W=$B/weights/py123d
export HF_TOKEN_PATH=/insomnia001/depts/edu/users/au2327/alpasim/.cache/hf/token HF_XET_HIGH_PERFORMANCE=1 HF_HUB_DISABLE_TELEMETRY=1 HOME=$TMPDIR
df -h /insomnia001/depts/edu/users/au2327 | tail -1
$B/envs/garage/bin/hf download kesai-labs/py123d_garage_pretrained_checkpoints --revision 56edbe90a71a3fd4baee2d5f2f2da0bb7e722364 \
  --include 'v0.2.0/ltf-base-joint64-68M/*' --include 'v0.2.0/ltf-streaming-joint64-68M/*' --local-dir $W > /dev/null
du -sh $W/v0.2.0/*; sha256sum $W/v0.2.0/*/posttrain/model_*.pth | cut -c1-16,65-
