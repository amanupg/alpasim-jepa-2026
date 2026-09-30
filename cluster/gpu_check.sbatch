#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_gpu
#SBATCH --gres=gpu:l40s:1
#SBATCH -c 8
#SBATCH --mem=48G
#SBATCH -t 00:40:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/gpu_check_%j.out
source /etc/profile
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; NR=/insomnia001/depts/edu/users/au2327/nureasoning
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
cd $B && env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=$B/envs/overlay:/insomnia001/depts/edu/users/au2327/alpasim/envs/overlay_driver:$B/src \
  $NR/ext/a15env/bin/python -u src/gpu_check.py 2>&1 | grep -v Warning
