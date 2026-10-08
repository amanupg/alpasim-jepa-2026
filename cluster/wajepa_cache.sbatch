#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_wjcache
#SBATCH --gres=gpu:A6000:1
#SBATCH -c 16
#SBATCH --mem=96G
#SBATCH -t 08:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/wajepa_cache_%A_%a.out
# Frozen WA-JEPA features for the route pilot (src/wajepa_route/cache_features.py), one array task per slice of
# logs of SPLIT (nuplan_train or nuplan_val). Anchors every SPACING s (default 4).
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
cd $B/ext/py123d_garage
PYTHONPATH=$B/src PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 $B/envs/garage-train/bin/python -m wajepa_route.cache_features \
  --data-root $B/data/py123d/nuplan/123D --split $SPLIT --out $B/data/wajepa_route \
  --repo $B/ext/WA-JEPA --config $B/ext/WA-JEPA/configs/wa_jepa_navsim_epdms.yaml \
  --checkpoint $B/weights/wa-jepa/model_state_dict.pt --anchor-spacing-s ${SPACING:-4} \
  --batch 8 --workers 14 --shard 64
du -sh $B/data/wajepa_route/$SPLIT
