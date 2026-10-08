#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_pyfetch
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 08:00:00
#SBATCH --array=0-11%6
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/py123d_fetch_%A_%a.out
# All nuPlan train + val sensor logs in 123D format (public kesai-labs/nuplan, nuPlan terms), for py123d training
# and the WA-JEPA route pilot: cameras l0, f0, r0, b0 + metadata, no lidar (the latent TransFuser uses none).
# Never nuplan_test: it holds navtest, which our local evaluation scenes come from.
# Array task i fetches every N-th log (interleaved), so tasks finish at similar times; re-running skips files
# already present (hf download checks them).
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
export PYTHONNOUSERSITE=1 HF_HUB_DISABLE_TELEMETRY=1
D=$B/data/py123d/nuplan/123D; cd $D
PY=$B/envs/garage-train/bin/python; HF=$B/envs/garage/bin/hf
I=${SLURM_ARRAY_TASK_ID:-0}; N=${SLURM_ARRAY_TASK_COUNT:-1}
$PY - $I $N > want_$I.txt <<'EOF'
import sys, pandas as pd
i, n = map(int, sys.argv[1:])
df = pd.read_parquet("index.parquet")
df = df[df.has_sensors & df.split.isin(["nuplan_train", "nuplan_val"])].sort_values(["split", "log_name"])
for k, (split, name) in enumerate(zip(df.split, df.log_name)):
    if k % n == i:
        print(f"logs/{split}/{name}/*")
EOF
echo "$(date -u +%T) task $I of $N: $(wc -l < want_$I.txt) logs"
ARGS=(); while read -r w; do ARGS+=(--include "$w"); done < want_$I.txt     # one pattern per flag
for c in l1 l2 r1 r2; do ARGS+=(--exclude "*/camera.pcam_$c.arrow"); done
ARGS+=(--exclude "*/lidar.lidar_merged.arrow")
t0=$(date +%s)
for attempt in 1 2 3; do
  $HF download kesai-labs/nuplan --repo-type dataset --local-dir . "${ARGS[@]}" > /dev/null && break
  echo "attempt $attempt failed, retrying in 60 s"; sleep 60
done
echo "$(date -u +%T) task $I done in $(( $(date +%s) - t0 )) s"
df -h /insomnia001 | tail -1
