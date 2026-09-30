#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_nup
#SBATCH --gres=gpu:l40s:1   # nuPlan MTGS renderer pins TORCH_CUDA_ARCH_LIST=8.9;9.0 (L40S/H100)
#SBATCH -c 12
#SBATCH --mem=120G
#SBATCH -t 03:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/sim_nuplan_%j.out
# Closed-loop nuPlan evaluation of the WA-JEPA driver on Insomnia.
# The AlpaSim tree ($A) is READ-ONLY here: its simulator sandboxes, nuPlan data, wizard and summary
# scripts are used as-is and mounted read-only; every output goes under $B (alpasim-jepa).
#   SCENES_FROM=<run dir with scene_ids.txt> (default: the AlpaSim v0.3 nuPlan bench run, for pairing)
#   NSCENES=N fallback; ROLLOUTS=2 (concurrent, as officially); TAG=name; WAJEPA_* passed to the driver
#   DRIVER=wajepa (default) | a15 (AlpaSim v0.3 Alpamayo driver, run read-only with its image settings)
#   NUPLAN_ROOT=<worldengine root> (default: the AlpaSim nuPlan data); SCENES_FROM=none to pick from it
source /etc/profile
module load apptainer/1.4.5
set -x
A=/insomnia001/depts/edu/users/au2327/alpasim; B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
NR=/insomnia001/depts/edu/users/au2327/nureasoning
SIF=$A/sandbox/alpasim-base; REPO=$A/external/alpasim
ROLLOUTS=${ROLLOUTS:-2}; NSCENES=${NSCENES:-100}; DRIVER=${DRIVER:-wajepa}
NUPLAN_ROOT=${NUPLAN_ROOT:-$A/data/nuplan_track}
RUN=$B/runs/nuplan_${DRIVER}${TAG:+_$TAG}_$SLURM_JOB_ID; mkdir -p $RUN
env | grep -E "^WAJEPA_|^A15_|^LTF_|^DIFFUSIONDRIVE_|^GTRS_" | sort > $RUN/variant.env; echo "NUPLAN_ROOT=$NUPLAN_ROOT" >> $RUN/variant.env
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
PORT_BASE=$((20000 + (SLURM_JOB_ID % 4000) * 10))
export ALPASIM_DRIVER_HOST=localhost ALPASIM_DRIVER_PORT=$((PORT_BASE + 9)) ALPASIM_NUPLAN_ROOT=$NUPLAN_ROOT
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE ":($PORT_BASE|$((PORT_BASE+1))|$((PORT_BASE+2))|$((PORT_BASE+3))|$((PORT_BASE+9)))$"; then
  echo "port block $PORT_BASE busy on $(hostname)"; exit 3
fi

if [ $DRIVER = a15 ]; then
# ---- driver: AlpaSim v0.3 (Alpamayo 1.5 int8), code and weights read-only, settings as in the v0.3 image
  HUB=$NR/.cache/hf/hub
  export A15_MODEL_DIR=$(ls -d $HUB/models--nvidia--Alpamayo-1.5-10B/snapshots/*/ | head -1)
  export A15_VLM_DIR=$(ls -d $HUB/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/*/ | head -1)
  export A15_PROCESSOR_DIR=$(ls -d $HUB/models--Qwen--Qwen3-VL-2B-Instruct/snapshots/*/ | head -1)
  export A15_INFERENCE_INTERVAL_US=${A15_INFERENCE_INTERVAL_US:-1000000}
  env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 \
      PYTHONPATH=$A/envs/overlay_driver:$A/envs/overlay_torchao:$A/src:$SIF/repo/src/grpc \
      $NR/ext/a15env/bin/python -u -m a15_driver.driver > $RUN/driver.log 2>&1 &
  READY="policy ready"
elif [ $DRIVER = image ]; then
# ---- driver: the submission image itself (apptainer sandbox of the docker image; its own ENV and code)
  IMG=${IMG:-$B/sandbox/wajepa-dev}
  # apptainer overrides the image HOME with the host home (read-only here): restore the image value
  apptainer exec --nv --cleanenv --writable-tmpfs --pwd /app --no-home \
      --env HOME=/tmp/home,ALPASIM_DRIVER_HOST=localhost,ALPASIM_DRIVER_PORT=$ALPASIM_DRIVER_PORT \
      $IMG python -m wajepa_challenge.driver > $RUN/driver.log 2>&1 &
  READY="warm-up done"
elif [ $DRIVER = ltf ] || [ $DRIVER = diffusiondrive ] || [ $DRIVER = gtrs ]; then
# ---- reference drivers: the organisers' SimScale samples, read-only from the upstream checkout, with the
#      env of their Dockerfiles (torch 2.8 here vs 2.6 in their images)
  E2E=$REPO/e2e_challenge; W=$B/weights/simscale
  case $DRIVER in
    ltf) PKG=navsim_transfuser_challenge; DIR=$E2E/sample_submission_simscale_navsim_transfuser
         export LTF_CHECKPOINT_PATH=$W/ltf_sim_navtest.ckpt LTF_DEVICE=cuda LTF_MAX_BATCH_SIZE=2 LTF_BATCH_WINDOW_MS=2 ;;
    diffusiondrive) PKG=navsim_diffusiondrive_challenge; DIR=$E2E/sample_submission_simscale_navsim_diffusiondrive
         export DIFFUSIONDRIVE_CHECKPOINT_PATH=$W/diffusiondrive_sim_navhard.ckpt DIFFUSIONDRIVE_DEVICE=cuda \
                DIFFUSIONDRIVE_MAX_BATCH_SIZE=1 DIFFUSIONDRIVE_BATCH_WINDOW_MS=2 ;;
    gtrs) PKG=navsim_gtrs_dense_challenge; DIR=$E2E/sample_submission_simscale_navsim_gtrs_dense
         export GTRS_CHECKPOINT_PATH=$W/gtrs_dense_resnet_sim_reward_navhard.ckpt GTRS_BACKBONE=resnet \
                GTRS_VOCAB_PATH=$W/navsim_16384.npy GTRS_SERVICE_VERSION=simscale-gtrs-dense-e2e \
                GTRS_DEVICE=cuda GTRS_SPEED_ENHANCEMENT=1 GTRS_MAX_BATCH_SIZE=1 GTRS_BATCH_WINDOW_MS=2 ;;
  esac
  env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 OMP_NUM_THREADS=1 TORCH_NUM_THREADS=1 \
      PYTHONPATH=$B/envs/overlay_samples:$A/envs/overlay_driver:$DIR \
      $NR/ext/a15env/bin/python -u -m $PKG.driver > $RUN/driver.log 2>&1 &
  READY="warm-up completed"
else
# ---- driver: WA-JEPA through the organisers' NAVSIM adapter (src/wajepa_challenge)
  export WAJEPA_REPO=$B/ext/WA-JEPA WAJEPA_CONFIG=$B/ext/WA-JEPA/configs/wa_jepa_navsim_epdms.yaml \
         WAJEPA_CHECKPOINT=$B/weights/wa-jepa/model_state_dict.pt
  env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 \
      PYTHONPATH=$B/envs/overlay:$A/envs/overlay_driver:$B/src \
      $NR/ext/a15env/bin/python -u -m wajepa_challenge.driver > $RUN/driver.log 2>&1 &
  READY="warm-up done"
fi
DRV=$!
trap 'kill $DRV 2>/dev/null' EXIT
for i in $(seq 1 120); do grep -q "$READY\|policy load failed" $RUN/driver.log && break; sleep 10; done
grep -q "$READY" $RUN/driver.log || { tail -40 $RUN/driver.log; exit 1; }
grep "loaded in\|$READY" $RUN/driver.log
( while kill -0 $DRV 2>/dev/null; do nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader >> $RUN/gpu_mem.log; sleep 15; done ) &

# ---- scenes: same list as the AlpaSim v0.3 bench run by default (paired comparison)
SCENES_FROM=${SCENES_FROM:-$(ls -d $A/runs/local_nuplan_a15_bench_* 2>/dev/null | tail -1)}
[ "$SCENES_FROM" = none ] && SCENES_FROM=
if [ -n "$SCENES_FROM" ] && [ -s "$SCENES_FROM/scene_ids.txt" ]; then
  SCENES=$(cat $SCENES_FROM/scene_ids.txt)
else
  SCENES=$(ls $NUPLAN_ROOT/navtest/assets | head -$NSCENES | sed "s/.*/'&'/" | paste -sd, -)
fi
echo "$SCENES" > $RUN/scene_ids.txt; echo "scenes from: ${SCENES_FROM:-first $NSCENES assets}" > $RUN/scenes_source.txt
SEL="\"scenes.scene_ids=[$SCENES]\" scenes.limit_to_first_n=0"

# ---- simulator (wizard writes compose + configs under $RUN; alpasim tree bound read-only)
mkdir -p $B/data/fs
{
  echo "cd $RUN"
  echo "exec /repo/.venv/bin/alpasim_wizard +e2e_challenge_nuplan=dev wizard.run_method=NONE wizard.log_dir=$RUN" \
       "defines.filesystem=$B/data/fs hydra.run.dir=$RUN/hydra eval.video.render_video=${VIDEO:-false} wizard.baseport=$PORT_BASE" \
       "runtime.endpoints.driver.n_concurrent_rollouts=$ROLLOUTS $SEL"
} > $RUN/wizard.sh
apptainer exec -B $A:$A:ro -B $B $SIF bash $RUN/wizard.sh > $RUN/wizard.log 2>&1 || { tail -40 $RUN/wizard.log; exit 1; }
apptainer exec -B $B $SIF /repo/.venv/bin/python -c "import yaml,json; json.dump(yaml.safe_load(open('$RUN/docker-compose.yaml')), open('$RUN/docker-compose.json','w'), indent=1)"
python3 $B/src/compose_apptainer.py $RUN/docker-compose.json --sif-dir $A/sandbox --repo-host $REPO \
  --logdir $RUN/svc-logs --cache-dir $B/cache/containers
RC=$?
echo "runtime exit $RC"
python3 $A/src/summarize_run.py $RUN
[ -n "$SCENES_FROM" ] && python3 $A/src/compare_runs.py $SCENES_FROM $RUN
echo "driver (pid $DRV) peak GPU memory: $(grep "^$DRV," $RUN/gpu_mem.log | sort -t, -k2 -n | tail -1)"
grep "inference=\|closed session" $RUN/driver.log | tail -3
exit $RC
