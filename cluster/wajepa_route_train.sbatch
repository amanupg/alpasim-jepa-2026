#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_wjtrain
#SBATCH --gres=gpu:A6000:1
#SBATCH -c 8
#SBATCH --mem=96G
#SBATCH -t 12:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/wajepa_route_train_%j.out
# WA-JEPA route pilot: trajectory stream + target-point encoder on cached features (src/wajepa_route/train_route.py).
#   TAG (run name), EXTRA (e.g. --no-target-point for the control, --epochs 3, --lr 5e-5)
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
cd $B/ext/py123d_garage
PYTHONPATH=$B/src PYTHONNOUSERSITE=1 HF_HUB_OFFLINE=1 $B/envs/garage-train/bin/python -m wajepa_route.train_route \
  --cache $B/data/wajepa_route --out $B/runs/wajepa_route_${TAG:-route}_$SLURM_JOB_ID \
  --repo $B/ext/WA-JEPA --config $B/ext/WA-JEPA/configs/wa_jepa_navsim_epdms.yaml \
  --checkpoint $B/weights/wa-jepa/model_state_dict.pt ${EXTRA:-}
