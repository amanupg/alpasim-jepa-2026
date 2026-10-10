#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_wjlocal
#SBATCH --gres=gpu:A6000:1
#SBATCH -c 16
#SBATCH --mem=160G
#SBATCH -t 12:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/wajepa_route_local_%j.out
# WA-JEPA route pilot entirely on the node's /local disk (the dept fileset has no room; Aman 2026-10-08):
#   1. batches of nuPlan 123D logs (cameras l0/f0/r0/b0 + metadata) -> frozen WA-JEPA features -> delete the batch's
#      raw logs, until NTRAIN train logs (every k-th log of the index) and NVAL val logs are encoded or the feature
#      budget (FEAT_GB) is reached; the next batch downloads while the current one encodes;
#   2. train the route run, then the control without the route input, on the same features (train_route.py);
#   only logs and the small trainable-tensor checkpoints go to the shared runs/ dir. /local is wiped at job end.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; T=${TMPDIR:?}
NTRAIN=${NTRAIN:-200}; NVAL=${NVAL:-12}; BATCH_LOGS=${BATCH_LOGS:-12}; FEAT_GB=${FEAT_GB:-100}; MIN_FREE_GB=${MIN_FREE_GB:-25}
RUN=$B/runs/wajepa_route_local_$SLURM_JOB_ID; mkdir -p $RUN
# Aman 2026-10-10: authenticated downloads with the AlpaSim HF account (anonymous ones were throttled to ~1 MB/s).
# Only the token FILE path is passed (never the token on a command line); the file is read in place.
export HF_TOKEN_PATH=/insomnia001/depts/edu/users/au2327/alpasim/.cache/hf/token
D=$T/nuplan/123D; F=$T/feat; mkdir -p $D $F
cp -r $B/data/py123d/nuplan/123D/index.parquet $B/data/py123d/nuplan/123D/maps $D/
export PYTHONNOUSERSITE=1 HF_HUB_DISABLE_TELEMETRY=1 HOME=$T/home PYTHONPATH=$B/src
PY=$B/envs/garage-train/bin/python; HF=$B/envs/garage/bin/hf
free_gb() { df -BG --output=avail /local | tail -1 | tr -dc 0-9; }
echo "local free at start: $(free_gb) GB"; nvidia-smi --query-gpu=name --format=csv,noheader
cd $D
$PY - $NTRAIN $NVAL $BATCH_LOGS > batches.txt <<'EOF'
import sys, pandas as pd
ntr, nva, bl = map(int, sys.argv[1:])
df = pd.read_parquet("index.parquet"); df = df[df.has_sensors]
pick = []
for split, n in (("nuplan_val", nva), ("nuplan_train", ntr)):
    names = sorted(df[df.split == split].log_name)
    step = max(1, len(names) // n)
    pick += [(split, x) for x in names[::step][:n]]          # spread over the whole split (dates, cities)
for i in range(0, len(pick), bl):
    print(" ".join(f"{s}/{x}" for s, x in pick[i:i + bl]))
EOF
echo "$(wc -l < batches.txt) batches"
fetch() {   # $1 = batch line -> downloads into $D/logs
  local ARGS=(); for x in $1; do ARGS+=(--include "logs/$x/*"); done
  for c in l1 l2 r1 r2; do ARGS+=(--exclude "*/camera.pcam_$c.arrow"); done; ARGS+=(--exclude "*/lidar.lidar_merged.arrow")
  for attempt in 1 2 3; do
    timeout 1800 $HF download kesai-labs/nuplan --repo-type dataset --local-dir $D "${ARGS[@]}" > /dev/null 2>> $RUN/fetch.err && return 0
    echo "fetch attempt $attempt failed: $(tail -2 $RUN/fetch.err | cut -c1-200)"; sleep 30
  done
  return 1
}
encode() {  # $1 = batch line, $2 = batch index
  for split in nuplan_val nuplan_train; do
    # (an if, not "test && echo": a false last test would make the loop fail and set -e end the job silently)
    logs=$(for x in $1; do if [[ $x == $split/* ]]; then echo ${x#*/}; fi; done | paste -sd, -)
    [ -z "$logs" ] && continue
    (cd $B/ext/py123d_garage && HF_HUB_OFFLINE=1 timeout 2400 $PY -m wajepa_route.cache_features --data-root $D --split $split --out $F \
      --repo $B/ext/WA-JEPA --config $B/ext/WA-JEPA/configs/wa_jepa_navsim_epdms.yaml \
      --checkpoint $B/weights/wa-jepa/model_state_dict.pt --anchor-spacing-s ${SPACING:-4} --logs $logs \
      --task $2 --tasks 1 --batch 8 --workers 14 --shard 64) > $RUN/encode_$2_$split.log 2>&1 \
      || { echo "encode $2 $split failed or timed out (skipped):"; tail -3 $RUN/encode_$2_$split.log; continue; }
    grep -E "scenes|done" $RUN/encode_$2_$split.log | cut -c1-200
  done
}
mapfile -t BL < batches.txt
t0=$(date +%s); fetch "${BL[0]}"
for i in "${!BL[@]}"; do
  n=$((i + 1)); PREF=""
  if [ $n -lt ${#BL[@]} ]; then fetch "${BL[$n]}" & PREF=$!; fi
  encode "${BL[$i]}" $i
  for x in ${BL[$i]}; do rm -rf $D/logs/$x; done                    # raw logs of this batch are no longer needed
  [ -n "$PREF" ] && { wait $PREF || echo "fetch of batch $n failed (its logs are skipped)"; }
  fg=$(du -s --block-size=1G $F | cut -f1)
  echo "$(date -u +%T) batch $i done: features ${fg} GB, local free $(free_gb) GB, $(( $(date +%s) - t0 )) s"
  if [ $fg -ge $FEAT_GB ] || [ $(free_gb) -lt $MIN_FREE_GB ] || [ $(( $(date +%s) - t0 )) -gt $(( ${DATA_HOURS:-6} * 3600 )) ]; then
    echo "stopping data at batch $i (feature budget, local disk or DATA_HOURS)"; rm -rf $D/logs; break
  fi
done
echo "train shards $(ls $F/nuplan_train | wc -l), val shards $(ls $F/nuplan_val | wc -l)"
cd $B/ext/py123d_garage
# MODES: name:extra-args entries (default: the first pilot's two runs)
MODES=${MODES:-"route: control:--no-target-point"}
for entry in $MODES; do
  mode=${entry%%:*}; X=$(echo "${entry#*:}" | tr "," " ")
  HF_HUB_OFFLINE=1 $PY -m wajepa_route.train_route --cache $F --out $RUN/$mode \
    --repo $B/ext/WA-JEPA --config $B/ext/WA-JEPA/configs/wa_jepa_navsim_epdms.yaml \
    --checkpoint $B/weights/wa-jepa/model_state_dict.pt --epochs ${EPOCHS:-3} --eval-every ${EVAL_EVERY:-1000} $X ${EXTRA:-} \
    > $RUN/train_$mode.log 2>&1 || { echo "training $mode failed:"; tail -15 $RUN/train_$mode.log; }
  grep -E '"event": "(start|eval)"' $RUN/train_$mode.log | cut -c1-600 || true
done
ls -la $RUN/route $RUN/control
