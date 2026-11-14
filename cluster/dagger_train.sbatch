#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_dagt
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|l40|h100|A6000|R6000
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 02:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/dagger_train_%j.out
# Fine-tune W1's planning decoder on DAgger samples (src/g2_dagger/train.py). DATA="dir ...", OUT=<dir>, ARGS=extra flags.
source /etc/profile
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
W1=$B/weights/py123d/v0.2.0/ltf-base-waypoints-68M/posttrain/model_1.pth
source $B/cluster/garage2_env.sh || exit 5
nvidia-smi --query-gpu=name --format=csv,noheader
env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HOME=$TMPDIR/home PYTHONPATH=$B/src \
  $G2PY -u -m g2_dagger.train --data ${DATA:?} --ckpt ${CKPT:-$W1} --out ${OUT:?} ${ARGS:-}
