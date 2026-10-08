#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_pycache
#SBATCH -c 16
#SBATCH --mem=96G
#SBATCH -t 08:00:00
#SBATCH --array=0-15
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/py123d_cache_%A_%a.out
# Latent TransFuser feature cache for all fetched nuPlan train + val logs (py123d's own sharded builder, as
# scripts/cache/nuplan/build_latent_transfuser_cache.sh). Scenes already stored are skipped.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
export PY123D_GARAGE_DATA_ROOT=$B/data/py123d PYTHONNOUSERSITE=1
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMBA_THREADING_LAYER=workqueue
cd $B/ext/py123d_garage
$B/envs/garage-train/bin/python -m py123d_garage.cache.build_cache \
  training@plan=py123d_garage.config.presets.python.training.latent_transfuser:ltf_nuplan_trainval \
  hydra.run.dir=$B/runs/py123d_cache_${SLURM_ARRAY_JOB_ID}/shard_${SLURM_ARRAY_TASK_ID} \
  shard_index=${SLURM_ARRAY_TASK_ID} shard_count=${SLURM_ARRAY_TASK_COUNT} cache_id=${SLURM_ARRAY_JOB_ID} \
  dataloader_config.num_workers=${SLURM_CPUS_PER_TASK}
du -sh $PY123D_GARAGE_DATA_ROOT/nuplan/py123d_garage_cache/*
