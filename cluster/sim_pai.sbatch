#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_pai
#SBATCH --gres=gpu:R6000:1   # NRE (PAI renderer) needs driver >= 575: Blackwell nodes
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 05:00:00   # as the AlpaSim PAI bench jobs (gres name is case-sensitive: R6000)
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/sim_pai_%j.out
# Zero-shot WA-JEPA on the PAI track (diagnostic): the WA-JEPA driver with WAJEPA_RIG=pai
# (NVIDIA cameras mapped onto WA-JEPA's nuPlan slots, 0.5 s history from the 10 Hz stream, a new
# plan every 0.5 s), on the same curated-val scenes as an AlpaSim v0.3 PAI bench run.
# The AlpaSim tree ($A) is READ-ONLY: its scene files are reached through symlinks in our own
# nre-artifacts folder (the wizard writes its sceneset folders there) and bound read-only.
#   VIEW=crop|resize  SCENES_FROM=<alpasim PAI run> (scene ids from its wizard.sh)  ROLLOUTS=4  TAG=name
source /etc/profile
module load apptainer/1.4.5
set -x
A=/insomnia001/depts/edu/users/au2327/alpasim; B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
NR=/insomnia001/depts/edu/users/au2327/nureasoning
SIF=$A/sandbox/alpasim-base; REPO=$A/external/alpasim
VIEW=${VIEW:-crop}; ROLLOUTS=${ROLLOUTS:-4}
SCENES_FROM=${SCENES_FROM:-$A/runs/local_pai_a15_bench1_12991558}
RUN=$B/runs/pai_wajepa_${VIEW}${TAG:+_$TAG}_$SLURM_JOB_ID; mkdir -p $RUN
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
PORT_BASE=$((20000 + (SLURM_JOB_ID % 4000) * 10))
export ALPASIM_DRIVER_HOST=localhost ALPASIM_DRIVER_PORT=$((PORT_BASE + 9))
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE ":($PORT_BASE|$((PORT_BASE+1))|$((PORT_BASE+2))|$((PORT_BASE+3))|$((PORT_BASE+9)))$"; then
  echo "port block $PORT_BASE busy on $(hostname)"; exit 3
fi

# ---- our own nre-artifacts view of the AlpaSim PAI scene files
# (the wizard reads both defines.sensordata and scenes.scene_cache as ${defines.filesystem}/nre-artifacts)
PD=$B/data/fs/nre-artifacts; mkdir -p $PD/scenesets $PD/ego-hoods
# an earlier wizard run may have created an empty all-usdzs dir here: replace it with the symlink
[ -L $PD/all-usdzs ] || { rm -f $PD/all-usdzs/all-usdzs; rmdir $PD/all-usdzs 2>/dev/null; ln -s $A/data/fs/nre-artifacts/all-usdzs $PD/all-usdzs; }
[ -L $PD/all-usdzs ] || { echo "could not link all-usdzs"; exit 1; }

# ---- driver: WA-JEPA, PAI rig mapping
export WAJEPA_RIG=pai WAJEPA_PAI_VIEW=$VIEW
env | grep -E "^WAJEPA_" | sort > $RUN/variant.env
env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 \
    WAJEPA_REPO=$B/ext/WA-JEPA WAJEPA_CONFIG=$B/ext/WA-JEPA/configs/wa_jepa_navsim_epdms.yaml \
    WAJEPA_CHECKPOINT=$B/weights/wa-jepa/model_state_dict.pt \
    PYTHONPATH=$B/envs/overlay:$A/envs/overlay_driver:$B/src \
    $NR/ext/a15env/bin/python -u -m wajepa_challenge.driver > $RUN/driver.log 2>&1 &
DRV=$!
trap 'kill $DRV 2>/dev/null' EXIT
for i in $(seq 1 90); do grep -q "warm-up done\|policy load failed" $RUN/driver.log && break; sleep 10; done
grep -q "warm-up done" $RUN/driver.log || { tail -40 $RUN/driver.log; exit 1; }
( while kill -0 $DRV 2>/dev/null; do nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader >> $RUN/gpu_mem.log; sleep 15; done ) &

# ---- scenes: the same clipgt ids as the paired AlpaSim v0.3 run
IDS=$(grep -o "clipgt-[0-9a-f-]*" $SCENES_FROM/wizard.sh | sort -u)
echo "$IDS" > $RUN/scene_ids.txt; echo "scenes from: $SCENES_FROM ($(echo "$IDS" | wc -l))" > $RUN/scenes_source.txt
SEL="+nurec_scenes=curated_val scenes.test_suite_id=null \"scenes.scene_ids=[$(echo "$IDS" | sed "s/.*/'&'/" | paste -sd, -)]\" scenes.limit_to_first_n=0"

# ---- simulator (wizard writes compose + configs under $RUN; alpasim tree bound read-only)
mkdir -p $B/data/fs $B/cache/hf
{
  echo "cd $RUN"
  echo "export HF_HOME=$B/cache/hf HF_HUB_OFFLINE=1"
  echo "exec /repo/.venv/bin/alpasim_wizard +e2e_challenge=dev wizard.run_method=NONE wizard.log_dir=$RUN" \
       "defines.filesystem=$B/data/fs defines.hf_cache=$B/cache/hf" \
       "hydra.run.dir=$RUN/hydra eval.video.render_video=${VIDEO:-false} wizard.baseport=$PORT_BASE" \
       "runtime.endpoints.driver.n_concurrent_rollouts=$ROLLOUTS $SEL"
} > $RUN/wizard.sh
apptainer exec -B $A:$A:ro -B $B $SIF bash $RUN/wizard.sh > $RUN/wizard.log 2>&1 || { tail -40 $RUN/wizard.log; exit 1; }
apptainer exec -B $B $SIF /repo/.venv/bin/python -c "import yaml,json; json.dump(yaml.safe_load(open('$RUN/docker-compose.yaml')), open('$RUN/docker-compose.json','w'), indent=1)"
python3 $B/src/compose_apptainer.py $RUN/docker-compose.json --sif-dir $A/sandbox --repo-host $REPO \
  --logdir $RUN/svc-logs --cache-dir $B/cache/containers --extra-bind $A/data/fs/nre-artifacts/all-usdzs
RC=$?
echo "runtime exit $RC"
python3 $A/src/summarize_run.py $RUN
python3 $A/src/compare_runs.py ${BASE:-$SCENES_FROM} $RUN
echo "driver (pid $DRV) peak GPU memory: $(grep "^$DRV," $RUN/gpu_mem.log | sort -t, -k2 -n | tail -1)"
grep "pai camera" $RUN/driver.log | sort -u -t' ' -k6,6 | head -4
grep "model_inference" $RUN/driver.log | tail -2
exit $RC
