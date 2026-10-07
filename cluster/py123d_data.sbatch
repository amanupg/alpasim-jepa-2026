#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_pydata
#SBATCH -c 16
#SBATCH --mem=96G
#SBATCH -t 12:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/py123d_data_%j.out
# nuPlan in 123D format (public kesai-labs/nuplan, nuPlan terms) for py123d fine-tuning: download sensor logs
# (3 front cameras + lidar + metadata, as the py123d docs) and build the latent TransFuser feature cache.
# Only nuplan_train / nuplan_val: nuplan_test holds navtest, which our local evaluation scenes come from.
#   NTRAIN, NVAL: how many logs of each split (first N in index order after SKIP); STEP=fetch|cache|both
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
export PY123D_GARAGE_DATA_ROOT=$B/data/py123d PYTHONNOUSERSITE=1 HF_HUB_DISABLE_TELEMETRY=1
D=$PY123D_GARAGE_DATA_ROOT/nuplan/123D; mkdir -p $D
PY=$B/envs/garage-train/bin/python; HF=$B/envs/garage/bin/hf
NTRAIN=${NTRAIN:-8}; NVAL=${NVAL:-2}; SKIP=${SKIP:-0}; STEP=${STEP:-both}
cd $D
if [ $STEP != cache ]; then
  [ -s index.parquet ] || $HF download kesai-labs/nuplan --repo-type dataset --local-dir . --include index.parquet --include 'maps/*'
  $PY - "$NTRAIN" "$NVAL" "$SKIP" > want.txt <<'EOF'
import sys, pandas as pd
ntr, nva, skip = map(int, sys.argv[1:])
df = pd.read_parquet("index.parquet"); df = df[df.has_sensors]
for split, n in (("nuplan_train", ntr), ("nuplan_val", nva)):
    for name in df[df.split == split].log_name.iloc[skip:skip + n]:
        print(f"logs/{split}/{name}/*")
EOF
  echo "$(date -u +%T) fetching $(wc -l < want.txt) logs"; t0=$(date +%s)
  ARGS=(); while read -r w; do ARGS+=(--include "$w"); done < want.txt     # the hf CLI takes one pattern per flag
  for c in b0 l1 l2 r1 r2; do ARGS+=(--exclude "*/camera.pcam_$c.arrow"); done
  $HF download kesai-labs/nuplan --repo-type dataset --local-dir . "${ARGS[@]}" > /dev/null
  t1=$(date +%s); GB=$(du -sb logs | awk '{print $1/1e9}')
  echo "fetch: $((t1-t0)) s, logs dir now $GB GB, $(ls logs/nuplan_train | wc -l) train + $(ls logs/nuplan_val 2>/dev/null | wc -l) val logs"
fi
if [ $STEP != fetch ]; then
  cd $B/ext/py123d_garage; t0=$(date +%s)
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMBA_THREADING_LAYER=workqueue \
  $PY -m py123d_garage.cache.build_cache \
    training@plan=py123d_garage.config.presets.python.training.latent_transfuser:ltf_nuplan_trainval \
    hydra.run.dir=$B/runs/py123d_cache_$SLURM_JOB_ID shard_index=0 shard_count=1 cache_id=$SLURM_JOB_ID \
    dataloader_config.num_workers=16
  t1=$(date +%s)
  echo "cache: $((t1-t0)) s"; du -sh $PY123D_GARAGE_DATA_ROOT/nuplan/py123d_garage_cache/* 2>/dev/null
fi
df -h /insomnia001 | tail -1
