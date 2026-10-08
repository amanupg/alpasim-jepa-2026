#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_plocal
#SBATCH --gres=gpu:A6000:1
#SBATCH -c 16
#SBATCH --mem=120G
#SBATCH -t 02:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/py123d_local_probe_%j.out
# Node-local data test (shared storage stays untouched apart from small logs/checkpoints): fetch 3 train + 1 val
# nuPlan logs into the job's /local dir, build the py123d cache there, delete the camera files (keep the small
# metadata the scene listing reads), then train one epoch from the cache. /local is wiped when the job ends.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; T=${TMPDIR:?}; mkdir -p $T/nuplan/123D
df -h /local | tail -1
export PY123D_GARAGE_DATA_ROOT=$T PYTHONNOUSERSITE=1 HF_HUB_DISABLE_TELEMETRY=1 HOME=$T/home
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMBA_THREADING_LAYER=workqueue
D=$T/nuplan/123D; cp -r $B/data/py123d/nuplan/123D/index.parquet $B/data/py123d/nuplan/123D/maps $D/
PY=$B/envs/garage-train/bin/python; HF=$B/envs/garage/bin/hf
cd $D
$PY - > want.txt <<'EOF'
import pandas as pd
df = pd.read_parquet("index.parquet"); df = df[df.has_sensors].sort_values(["split", "log_name"])
for split, n in (("nuplan_train", 3), ("nuplan_val", 1)):
    for name in df[df.split == split].log_name.iloc[200:200 + n]:
        print(f"logs/{split}/{name}/*")
EOF
ARGS=(); while read -r w; do ARGS+=(--include "$w"); done < want.txt
for c in l1 l2 r1 r2; do ARGS+=(--exclude "*/camera.pcam_$c.arrow"); done; ARGS+=(--exclude "*/lidar.lidar_merged.arrow")
t0=$(date +%s); $HF download kesai-labs/nuplan --repo-type dataset --local-dir . "${ARGS[@]}" > /dev/null
echo "fetch $(( $(date +%s) - t0 )) s; $(du -sh logs | cut -f1)"
cd $B/ext/py123d_garage
t0=$(date +%s)
$PY -m py123d_garage.cache.build_cache \
  training@plan=py123d_garage.config.presets.python.training.latent_transfuser:ltf_nuplan_trainval \
  hydra.run.dir=$T/cache_run shard_index=0 shard_count=1 cache_id=$SLURM_JOB_ID dataloader_config.num_workers=16 2>&1 | grep -E "Cached|scenes from" | cut -c1-200
echo "cache $(( $(date +%s) - t0 )) s; $(du -sh $T/nuplan/py123d_garage_cache | cut -f1)"
find $D/logs -name "camera.*.arrow" -delete
echo "after deleting cameras: logs $(du -sh $D/logs | cut -f1)"; ls $D/logs/nuplan_train/* | head -12
unset SLURM_TRES_PER_TASK
srun -n 1 --cpus-per-task=16 $PY -m py123d_garage.training.train \
  training=py123d_garage.config.presets.python.training.latent_transfuser:ltf_nuplan_trainval \
  compile_mode=default hydra.run.dir=$T/train_run \
  policy_config.transfuser_config.planning_config.use_planning_decoder=true \
  initial_weights_file="'$B/weights/py123d/resnet34_v0.1.0/model_0014.pth'" initial_weights_strict=true \
  wandb_config.enabled=false lightning_trainer_config.devices=1 lightning_trainer_config.max_epochs=1 \
  dataloader_config.batch_size=64 dataloader_config.num_workers=16 2>&1 | grep -E "train samples|scenes passed|Training finished|Error|error|Traceback" | cut -c1-250 &
P=$!; for i in $(seq 1 60); do kill -0 $P 2>/dev/null || break; sleep 20; done; kill $P 2>/dev/null || true
df -h /local | tail -1
