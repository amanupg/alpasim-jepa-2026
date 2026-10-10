#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_pylocal
#SBATCH --gres=gpu:A6000:1
#SBATCH --ntasks-per-node=1
#SBATCH -c 24
#SBATCH --mem=180G
#SBATCH -t 12:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/py123d_local_train_%j.out
# py123d training with all data on the node's /local disk (Aman 2026-10-08: the dept fileset has no room).
#   1. NLOGS nuPlan train+val logs, spread over the index (every k-th log, val share as in the dataset), fetched in
#      batches of BATCH_LOGS (3 front cameras + metadata, no lidar); each batch is cached by py123d's own builder,
#      then its camera files are deleted (training lists scenes from the metadata and reads tensors from the cache;
#      verified 2026-10-08). The next batch downloads while the current one caches. Stops early if /local runs low.
#   2. training as py123d_train.sbatch (STAGE, INIT, EPOCHS, KEEP, COMPILE, LR); checkpoints to RUN_DIR (shared).
# Multi-GPU: sbatch --gres=gpu:A6000:G --ntasks-per-node=G -c <cpus per GPU> (one srun task per GPU).
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; T=${TMPDIR:?}
NLOGS=${NLOGS:-430}; BATCH_LOGS=${BATCH_LOGS:-15}; MIN_FREE_GB=${MIN_FREE_GB:-30}
RUN=${RUN_DIR:-$B/runs/py123d_local${TAG:+_$TAG}_$SLURM_JOB_ID}; mkdir -p $RUN
export PY123D_GARAGE_DATA_ROOT=$T PYTHONNOUSERSITE=1 HF_HUB_DISABLE_TELEMETRY=1 HOME=$T/home PY123D_GARAGE_RUNTIME_TYPE_CHECKING=false
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMBA_THREADING_LAYER=workqueue
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True WANDB_MODE=disabled
# Aman 2026-10-10: authenticated downloads with the AlpaSim HF account (anonymous ones were throttled to ~1 MB/s).
# Only the token FILE path is passed (never the token on a command line); the file is read in place.
export HF_TOKEN_PATH=/insomnia001/depts/edu/users/au2327/alpasim/.cache/hf/token HF_XET_HIGH_PERFORMANCE=1
D=$T/nuplan/123D; mkdir -p $D $HOME; cp -r $B/data/py123d/nuplan/123D/index.parquet $B/data/py123d/nuplan/123D/maps $D/
PY=$B/envs/garage-train/bin/python; HF=$B/envs/garage/bin/hf
CPUS=$(( ${SLURM_CPUS_PER_TASK:-24} * ${SLURM_NTASKS_PER_NODE:-1} ))
free_gb() { df -BG --output=avail /local | tail -1 | tr -dc 0-9; }
echo "local free at start: $(free_gb) GB; $CPUS CPUs; $(nvidia-smi --list-gpus | wc -l) GPUs"
cd $D
$PY - $NLOGS $BATCH_LOGS ${OFFSET:-0} > batches.txt <<'EOF'
import sys, pandas as pd
n, bl, offset = map(int, sys.argv[1:])
df = pd.read_parquet("index.parquet"); df = df[df.has_sensors & df.split.isin(["nuplan_train", "nuplan_val"])]
df = df.sort_values(["split", "log_name"])
step = max(1, len(df) // n)
pick = [f"{s}/{x}" for s, x in zip(df.split, df.log_name)][offset::step][:n]   # OFFSET 0/1/2: disjoint thirds
# the preset has a train and a val source: the first cached batch must hold logs of both splits
first_val = next(i for i, p in enumerate(pick) if p.startswith("nuplan_val/"))
pick.insert(0, pick.pop(first_val))
for i in range(0, len(pick), bl):
    print(" ".join(pick[i:i + bl]))
EOF
echo "$(wc -l < batches.txt) batches of up to $BATCH_LOGS logs"
fetch() {   # 3 parallel downloads per batch, each into its own staging dir, moved into the data root when complete
  local x k=0 pids=() ok=0
  for x in $1; do echo "$x"; done | split -n r/${PAR:-3} - $T/stage_list_$2_
  for lst in $T/stage_list_$2_*; do
    ( S=$T/stage_$2_$k; mkdir -p $S; ARGS=(); while read -r y; do ARGS+=(--include "logs/$y/*"); done < $lst
      for c in l1 l2 r1 r2 b0; do ARGS+=(--exclude "*/camera.pcam_$c.arrow"); done; ARGS+=(--exclude "*/lidar.lidar_merged.arrow")
      for attempt in 1 2 3; do
        if timeout 3600 $HF download kesai-labs/nuplan --repo-type dataset --local-dir $S "${ARGS[@]}" > /dev/null 2>> $RUN/fetch.err; then
          while read -r y; do mkdir -p $D/logs/${y%%/*}; [ -d $S/logs/$y ] && mv $S/logs/$y $D/logs/$y; done < $lst
          rm -rf $S; exit 0
        fi
        echo "fetch $lst attempt $attempt failed"; sleep 30
      done
      exit 1 ) &
    pids+=($!); k=$((k + 1))
  done
  for p in "${pids[@]}"; do wait $p || ok=1; done
  rm -f $T/stage_list_$2_*
  return $ok
}
cache() {
  (cd $B/ext/py123d_garage && $PY -m py123d_garage.cache.build_cache \
    training@plan=py123d_garage.config.presets.python.training.latent_transfuser:ltf_nuplan_trainval \
    hydra.run.dir=$T/cache_run_$1 shard_index=0 shard_count=1 cache_id=${SLURM_JOB_ID}_$1 \
    dataloader_config.num_workers=$CPUS) > $RUN/cache_$1.log 2>&1 || { echo "cache $1 failed:"; tail -5 $RUN/cache_$1.log; return 1; }
  grep -h "Cached" $RUN/cache_$1.log | cut -c1-200
}
mapfile -t BL < batches.txt
t0=$(date +%s); fetch "${BL[0]}" 0
for i in "${!BL[@]}"; do
  n=$((i + 1)); PREF=""
  if [ $n -lt ${#BL[@]} ] && [ $(free_gb) -ge $MIN_FREE_GB ]; then fetch "${BL[$n]}" $n & PREF=$!; fi   # (fetched-but-uncached logs are removed below)
  cache $i
  for x in ${BL[$i]}; do rm -f $D/logs/$x/camera.*.arrow; done      # cached: training needs only the metadata
  [ -n "$PREF" ] && wait $PREF
  echo "$(date -u +%T) batch $i cached; cache $(du -s --block-size=1G $T/nuplan/py123d_garage_cache | cut -f1) GB, local free $(free_gb) GB, $(( $(date +%s) - t0 )) s"
  if [ -z "$PREF" ]; then [ $n -lt ${#BL[@]} ] && echo "stopping data after batch $i: local disk low"; break; fi
  if [ $(( $(date +%s) - t0 )) -gt $(( ${DATA_HOURS:-7} * 3600 )) ]; then                 # leave time to train
    echo "stopping data after batch $i: DATA_HOURS reached"; wait $PREF 2>/dev/null || true; break
  fi
done
# drop logs fetched but not cached (their scenes would fail the cache coverage check), and any staging dirs
for j in $(seq $((i + 1)) $(( ${#BL[@]} - 1 ))); do for x in ${BL[$j]}; do rm -rf $D/logs/$x; done; done; rm -rf $T/stage_*
echo "data ready in $(( $(date +%s) - t0 )) s: $(ls $D/logs/nuplan_train | wc -l) train + $(ls $D/logs/nuplan_val | wc -l) val logs; local free $(free_gb) GB"
cd $B/ext/py123d_garage
GPUS=$(nvidia-smi --list-gpus | wc -l); BATCH=${BATCH:-64}
INIT=${INIT:-$B/weights/py123d/resnet34_v0.1.0/model_0014.pth}
unset SLURM_TRES_PER_TASK
srun --kill-on-bad-exit=1 -n $GPUS --cpus-per-task=${SLURM_CPUS_PER_TASK:-24} $PY -m py123d_garage.training.train \
  training=py123d_garage.config.presets.python.training.latent_transfuser:ltf_nuplan_trainval \
  compile_mode=${COMPILE:-max-autotune} hydra.run.dir=$RUN \
  $([ "${STAGE:-post}" = pre ] && echo policy_config.transfuser_config.planning_config.use_planning_decoder=false \
     || echo policy_config.transfuser_config.planning_config.use_planning_decoder=true initial_weights_file="'$INIT'" initial_weights_strict=${STRICT:-true}) \
  wandb_config.enabled=false lightning_trainer_config.devices=$GPUS lightning_trainer_config.num_nodes=1 \
  lightning_trainer_config.max_epochs=${EPOCHS:-15} lightning_trainer_config.log_every_n_steps=50 \
  ${LR:+optimizer_config.learning_rate=$LR} ${KEEP:+epochs_to_keep_checkpoints_for=$KEEP} \
  dataloader_config.batch_size=$((BATCH / GPUS)) dataloader_config.num_workers=${SLURM_CPUS_PER_TASK:-24} \
  ${TRAIN_OVERRIDES:-} > $RUN/train.log 2>&1 &
PID=$!
while kill -0 $PID 2>/dev/null; do
  if grep -q "Training finished after" $RUN/train.log; then sleep 120; kill $PID 2>/dev/null || true; sleep 30; kill -9 $PID 2>/dev/null || true; break; fi
  sleep 60
done
wait $PID 2>/dev/null || true
set +eo pipefail       # reporting only from here; the exit status says whether training finished
grep -E "train samples|Epoch [0-9]+/[0-9]+ done|Training finished|Error|Traceback" $RUN/train.log | tail -40 | cut -c1-250
ls -la $RUN | head -30
grep -q "Training finished after" $RUN/train.log
