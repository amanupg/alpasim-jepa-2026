#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_nurec
#SBATCH --gres=gpu:R6000:1   # NRE (PAI renderer) needs driver >= 575: Blackwell nodes (gres name is case-sensitive)
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 05:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/sim_nurec_%j.out
# NuRec (PAI curated val) closed loop for the py123d v0.2.2 driver (garage2), as the host's published NuRec results:
# +e2e_challenge=dev (harmonizer on, take-over 1.7 s), +nurec_scenes=curated_val, 1 rollout per scene, default 2 Hz.
# Why (LEDGER 2026-11-10): the host's research log counts a change only if it helps on nuPlan AND NuRec ("single-track
# gains did not transfer to the leaderboard"), and NuRec local orders the 3 board-known released checkpoints correctly.
#   G2_CKPTS="<ckpt> [...]" (default joint64 posttrain seed 0), G2_MODULE=g2_addons.entry + G2_START_K etc. (v8 add-ons),
#   CHUNK=i NCHUNK=n: scenes i of n slices of the 441 (sorted), TAG=name, VIDEO=true|false, ROLLOUTS (concurrent, 1)
source /etc/profile
module load apptainer/1.4.5
set -x
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
SIF=$B/sandbox/alpasim-base; REPO=$B/ext/alpasim_sim
ROLLOUTS=${ROLLOUTS:-1}; CHUNK=${CHUNK:-0}; NCHUNK=${NCHUNK:-1}
RUN=$B/runs/nurec_garage2${TAG:+_$TAG}_c${CHUNK}of${NCHUNK}_$SLURM_JOB_ID; mkdir -p $RUN
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader | tee $RUN/gpu.txt
PORT_BASE=$((20000 + (SLURM_JOB_ID % 4000) * 10))
export ALPASIM_DRIVER_HOST=localhost ALPASIM_DRIVER_PORT=$((PORT_BASE + 9))
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE ":($PORT_BASE|$((PORT_BASE+1))|$((PORT_BASE+2))|$((PORT_BASE+3))|$((PORT_BASE+9)))$"; then
  echo "port block $PORT_BASE busy on $(hostname)"; exit 3
fi
env | grep -E "^G2_" | sort > $RUN/variant.env

# ---- driver: py123d_garage v0.2.2 natively (same as sim_nuplan.sbatch DRIVER=garage2), NuRec sensor rig of the checkpoint
# G2_SHADOW=1: shadow logging (src/g2_shadow, plans unchanged) into $RUN/shadow
[ "${G2_SHADOW:-0}" = 1 ] && { export G2_SHADOW_DIR=$RUN/shadow G2_MODULE=g2_shadow.entry; mkdir -p $G2_SHADOW_DIR; }
# G2_NUDGE_MODE=A|B: stall nudge (src/g2_nudge, candidate fix 1), firings logged into $RUN/nudge
[ -n "${G2_NUDGE_MODE:-}" ] && { export G2_NUDGE_LOG=$RUN/nudge G2_MODULE=g2_nudge.entry; mkdir -p $G2_NUDGE_LOG; }
source $B/cluster/garage2_env.sh || exit 5
V2=$B/weights/py123d/v0.2.0/ltf-base-joint64-68M/posttrain
read -ra _ck <<< "${G2_CKPTS:-$V2/model_0.pth}"
RIG=${G2_RIG:-$(dirname ${_ck[0]})/sensor_rig_nurec.yaml}
[ -f $(dirname ${_ck[0]})/config.yaml ] && [ -f $RIG ] || { echo "missing config.yaml or $RIG"; exit 5; }
env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HOME=$RUN/garage_home OMP_NUM_THREADS=8 MPLCONFIGDIR=$TMPDIR/mpl \
    ${G2_MODULE:+PYTHONPATH=$B/src} $G2PY -m ${G2_MODULE:-py123d_garage.evaluation.alpasim.evaluate} hydra.run.dir=$RUN/garage \
    "policy_config.evaluation_checkpoint_files=[$(IFS=,; echo "${_ck[*]}")]" \
    policy_config.evaluation_sensor_rig_file=$RIG \
    host=localhost port=$ALPASIM_DRIVER_PORT ${G2_OVERRIDES:-} > $RUN/driver.log 2>&1 &
DRV=$!
trap 'kill $DRV 2>/dev/null' EXIT
for i in $(seq 1 120); do grep -q "garage driver listening\|policy load failed\|Traceback" $RUN/driver.log && break; sleep 10; done
grep -q "garage driver listening" $RUN/driver.log || { tail -40 $RUN/driver.log; exit 1; }
( while kill -0 $DRV 2>/dev/null; do nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader >> $RUN/gpu_mem.log; sleep 15; done ) &

# ---- scenes: chunk CHUNK of NCHUNK of the sorted curated-val ids (or SCENE_IDS_FILE)
IDS_ALL=${SCENE_IDS_FILE:-$B/data/nurec_curated_val_ids.txt}
tr -d '\r' < $IDS_ALL | awk -v c=$CHUNK -v n=$NCHUNK 'NF && NR % n == c' > $RUN/scene_ids.txt   # id list has CRLF endings
[ -n "${NSCENES:-}" ] && { head -$NSCENES $RUN/scene_ids.txt > $RUN/s.tmp; mv $RUN/s.tmp $RUN/scene_ids.txt; }
echo "scenes: chunk $CHUNK of $NCHUNK from $IDS_ALL ($(wc -l < $RUN/scene_ids.txt))" > $RUN/scenes_source.txt
SEL="+nurec_scenes=curated_val scenes.test_suite_id=null \"scenes.scene_ids=[$(sed "s/.*/'&'/" $RUN/scene_ids.txt | paste -sd, -)]\" scenes.limit_to_first_n=0"

# ---- simulator (scenes are already in $B/data/fs/nre-artifacts from cluster/nurec_fetch.sbatch; offline here)
{
  echo "cd $RUN"
  echo "export HF_HOME=$B/.cache/hf HF_HUB_OFFLINE=1"
  echo "exec /repo/.venv/bin/alpasim_wizard +e2e_challenge=dev wizard.run_method=NONE wizard.log_dir=$RUN" \
       "defines.filesystem=$B/data/fs hydra.run.dir=$RUN/hydra eval.video.render_video=${VIDEO:-false} wizard.baseport=$PORT_BASE" \
       "runtime.endpoints.driver.n_concurrent_rollouts=$ROLLOUTS $SEL ${EXTRA_OVERRIDES:-}"
} > $RUN/wizard.sh
apptainer exec -B $B $SIF bash $RUN/wizard.sh > $RUN/wizard.log 2>&1 || { tail -40 $RUN/wizard.log; exit 1; }
apptainer exec -B $B $SIF /repo/.venv/bin/python -c "import yaml,json; json.dump(yaml.safe_load(open('$RUN/docker-compose.yaml')), open('$RUN/docker-compose.json','w'), indent=1)"
# image dir on the node's /local: links to the shared sandboxes, plus the NRE renderer unpacked from its .sif
# (cluster/nurec_fetch.sbatch PART=image) unless a shared sandbox of it exists
SD=$TMPDIR/sifdir; mkdir -p $SD; for d in $B/sandbox/*; do ln -s $d $SD/; done
if [ ! -d $B/sandbox/nre-ga_26.04/usr ]; then
  rm -f $SD/nre-ga_26.04
  APPTAINER_TMPDIR=$TMPDIR/at APPTAINER_CACHEDIR=$TMPDIR/ac apptainer build --sandbox $SD/nre-ga_26.04 $B/sif/nre-ga_26.04.sif > $RUN/sandbox.log 2>&1 \
    || { tail -20 $RUN/sandbox.log; exit 6; }
fi
TMPDIR=/tmp python3 $B/src/compose_apptainer.py $RUN/docker-compose.json --sif-dir $SD --repo-host $REPO \
  --logdir $RUN/svc-logs --cache-dir $B/cache/containers --timeout 3600
RC=$?
echo "runtime exit $RC"
python3 $B/src/tools/summarize_run.py $RUN
echo "driver (pid $DRV) peak GPU memory: $(grep "^$DRV," $RUN/gpu_mem.log | sort -t, -k2 -n | tail -1)"
apptainer exec -B $B $SIF env PYTHONDONTWRITEBYTECODE=1 /repo/.venv/bin/python $B/src/analysis/slim_asl.py --delete $RUN | tail -1
exit $RC
