#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_nup
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|l40|h100   # nuPlan MTGS renderer pins TORCH_CUDA_ARCH_LIST=8.9;9.0 (L40S/L40/H100)
#SBATCH -c 12
#SBATCH --mem=120G
#SBATCH -t 01:15:00   # runs take ~20-30 min; a short limit lets the scheduler backfill
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/sim_nuplan_%j.out
# Closed-loop nuPlan evaluation of the WA-JEPA driver on Insomnia.
# Since 2026-11-04 the simulator sandbox, checkout and nuPlan data live in this folder ($B/sandbox, $B/ext/alpasim_sim,
# $B/data/nuplan_track; moved from ../alpasim, which is gone). The a15 / SimScale-sample / wajepa drivers below still name
# ../alpasim/envs/overlay_driver, which was deleted with it: those drivers no longer run as is.
# scripts are used as-is and mounted read-only; every output goes under $B (alpasim-jepa).
#   SCENES_FROM=<run dir with scene_ids.txt> (default: the AlpaSim v0.3 nuPlan bench run, for pairing)
#   NSCENES=N fallback; ROLLOUTS=2 (concurrent, as officially); TAG=name; WAJEPA_* passed to the driver
#   DRIVER=wajepa (default) | a15 (AlpaSim v0.3 Alpamayo driver, run read-only with its image settings)
#   NUPLAN_ROOT=<worldengine root> (default: the AlpaSim nuPlan data); SCENES_FROM=none to pick from it
#   EXTRA_OVERRIDES="controller.gains.lat_position_weight=2.0 ...": wizard overrides (space separated; e.g. the MPC gains a
#   submission may set: long/lat_position_weight, heading_weight, acceleration_weight, rel_front_steering_angle_weight,
#   rel_acceleration_weight, idx_start_penalty; the nonlinear MPC is the default locally and officially)
#   LOCAL_PART=NNN: fresh held-out scenes from MTGS asset part NNN on the node-local disk (see below)
source /etc/profile
module load apptainer/1.4.5
set -x
A=/insomnia001/depts/edu/users/au2327/alpasim; B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
NR=/insomnia001/depts/edu/users/au2327/nureasoning
SIF=$B/sandbox/alpasim-base; REPO=${REPO:-$B/ext/alpasim_sim}   # moved from ../alpasim 2026-11-04
ROLLOUTS=${ROLLOUTS:-2}; NSCENES=${NSCENES:-100}; DRIVER=${DRIVER:-wajepa}
NUPLAN_ROOT=${NUPLAN_ROOT:-$B/data/nuplan_track}
RUN=$B/runs/nuplan_${DRIVER}${TAG:+_$TAG}_$SLURM_JOB_ID; mkdir -p $RUN
if [ -n "${LOCAL_PART:-}" ]; then
  # Fresh held-out scenes without using the dept fileset (full on 2026-10-08): build a track root on the node's
  # /local from the shared trajdata cache + configs and MTGS asset part LOCAL_PART, and drive only the scenes of
  # that part that are in none of our shared track copies (so never used for tuning or earlier checks).
  L=${TMPDIR:?}/nuplan_track
  # Under cluster/sim_nuplan_multi.sbatch (TMPDIR = <job tmp>/v<variant>) the part is built once per job and shared by
  # the variants run one after another (downloading it took ~45 min per variant on 2026-11-12).
  case $(basename $TMPDIR) in v*) L=$(dirname $TMPDIR)/nuplan_track_$LOCAL_PART;; esac
  if [ -d $L/navtest/assets ] && [ -n "$(ls $L/navtest/assets)" ]; then echo "part $LOCAL_PART: reusing $L"; else
  mkdir -p $L/navtest
  # trajdata cache + configs: symlinks to ../alpasim's copies (dedupe 2026-10-18; read-only, bound into the services
  # via --extra-bind below). Copying the 85k small files from GPFS took over 2 h and made earlier fresh runs time out.
  ln -sfn $B/data/nuplan_track/nuplan_test $L/nuplan_test; ln -sfn $B/data/nuplan_track/navtest/configs $L/navtest/configs
  # hf resumes interrupted transfers (a piped curl stream was cut off after ~3 GB on 2026-10-08)
  PC=$B/data/mtgs_parts/part$LOCAL_PART.tar.gz   # pre-fetched by cluster/fetch_parts.sbatch
  if [ -s $PC ]; then mkdir -p $TMPDIR/dl/MTGS_asset/navtest/assets; ln -sfn $PC $TMPDIR/dl/MTGS_asset/navtest/assets/part$LOCAL_PART.tar.gz; else
  for attempt in 1 2 3; do
    # token file path only, never the token itself (Aman 2026-10-10); high-performance xet for speed
    HOME=$TMPDIR/home HF_HUB_DISABLE_TELEMETRY=1 HF_XET_HIGH_PERFORMANCE=1 HF_TOKEN_PATH=$B/.cache/hf/token $B/envs/garage/bin/hf download OpenDriveLab/AlpasimChallenge2026_nuplan_track \
      --repo-type dataset --include "MTGS_asset/navtest/assets/part$LOCAL_PART.tar.gz" --local-dir $TMPDIR/dl > /dev/null && break
    sleep 60
  done
  fi
  tar -xzf $TMPDIR/dl/MTGS_asset/navtest/assets/part$LOCAL_PART.tar.gz -C $L || { echo "part $LOCAL_PART: download/extract failed"; exit 4; }
  rm -rf $TMPDIR/dl
  fi
  mkdir -p $RUN/heldout
  ls $L/navtest/assets | grep -vxFf <(ls $B/data/nuplan_track/navtest/assets) > $RUN/heldout/ids.txt || true
  head -${NSCENES} $RUN/heldout/ids.txt | sed "s/.*/'&'/" | paste -sd, - > $RUN/heldout/scene_ids.txt
  echo "part $LOCAL_PART: $(wc -l < $RUN/heldout/ids.txt) fresh scenes, driving $(head -${NSCENES} $RUN/heldout/ids.txt | wc -l)"
  NUPLAN_ROOT=$L; SCENES_FROM=$RUN/heldout
fi
# LOCAL_CACHE (default on once $B/data/nuplan_cache_hf holds both archives, cluster/fetch_nuplan_cache.sbatch): the
# trajdata cache + navtest/configs are extracted from their two public archives onto the node's /local; the scene
# assets stay where they are (symlinked, bound read-only). 2026-10-26: under fileset load the renderer's scan of the
# 85k shared cache files went from 4.5 min to > 40 min, timing out every run (big-file reads stayed fast).
ASSET_BIND=; HFC=$B/data/nuplan_cache_hf
if [ "${LOCAL_CACHE:-1}" = 1 ] && [ -s $HFC/nuplan_test.tar.gz ] && [ -s $HFC/configs.tar.gz ]; then
  LC=${TMPDIR:?}/nuplan_local; mkdir -p $LC
  t0=$(date +%s)
  tar -xzf $HFC/nuplan_test.tar.gz -C $LC && tar -xzf $HFC/configs.tar.gz -C $LC || { echo "cache extract failed"; exit 4; }
  ASSET_BIND=$(readlink -f $NUPLAN_ROOT/navtest/assets); ln -s $ASSET_BIND $LC/navtest/assets
  echo "node-local trajdata cache in $(( $(date +%s) - t0 )) s ($(ls $LC/nuplan_test | wc -l) entries, $(ls $LC/navtest/configs | wc -l) configs); assets from $ASSET_BIND"
  NUPLAN_ROOT=$LC
fi
env | grep -E "^WAJEPA_|^A15_|^LTF_|^DIFFUSIONDRIVE_|^GTRS_|^GARAGE_" | sort > $RUN/variant.env; echo "NUPLAN_ROOT=$NUPLAN_ROOT" >> $RUN/variant.env
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
elif [ $DRIVER = garage ]; then
# ---- driver: py123d_garage (kesai-labs, Apache-2.0) v0.1.1 with its public checkpoint resnet34_v0.1.0/model_0014.pth
#      and the nuPlan sensor rig, as in the checkpoint README (official entries with it: 0.848 / PCS ~1485)
  W=${GARAGE_W:-$B/weights/py123d/resnet34_v0.1.0}     # GARAGE_W: a training run dir (config.yaml + sensor rigs + model_NNNN.pth)
  # GARAGE_RIG: our node-local runs export a rig without cameras (camera files deleted after caching): pass the public nuPlan rig
  export GARAGE_GTRS_CHECKPOINT=$B/weights/simscale/gtrs_dense_resnet_sim_reward_navhard.ckpt \
         GARAGE_GTRS_VOCAB=$B/weights/simscale/navsim_16384.npy     # used only with GARAGE_JUDGE=gtrs
  env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HOME=$RUN/garage_home OMP_NUM_THREADS=8 \
      PYTHONPATH=$B/src $B/envs/garage/bin/python -m garage_addons.entry hydra.run.dir=$RUN/garage \
      policy_config.evaluation_checkpoint_file=$W/${GARAGE_CKPT:-model_0014.pth} \
      policy_config.evaluation_sensor_rig_file=${GARAGE_RIG:-$W/sensor_rig_0.yaml} \
      host=localhost port=$ALPASIM_DRIVER_PORT device=cuda ${GARAGE_OVERRIDES:-} > $RUN/driver.log 2>&1 &
  READY="garage driver listening"
elif [ $DRIVER = garage2 ]; then
# ---- driver: py123d_garage v0.2.2 (kesai-labs, Apache-2.0) natively, from a node-local env (cluster/garage2_env.sh), with
#      its released v0.2.0 checkpoints; the same module and config as the N submission images. For fast A/B of driver
#      settings and checkpoints:
#      G2_CKPTS="<file> [<file> ...]" (several = ensemble, plans averaged; default joint64 posttrain seed 0),
#      G2_RIG (default the checkpoint dir's sensor_rig_nuplan.yaml), G2_OVERRIDES (driver settings, e.g. route_memory=true)
#      G2_MODULE=g2_addons.entry: our add-ons around the same driver (src/g2_addons; G2_START_* env, start-from-rest)
# G2_SHADOW=1: shadow logging (src/g2_shadow, plans unchanged) into $RUN/shadow
  [ "${G2_SHADOW:-0}" = 1 ] && { export G2_SHADOW_DIR=$RUN/shadow G2_MODULE=g2_shadow.entry; mkdir -p $G2_SHADOW_DIR; }
# G2_NUDGE_MODE=A|B: stall nudge (src/g2_nudge, candidate fix 1; G2_NUDGE_* env), firings logged into $RUN/nudge
  [ -n "${G2_NUDGE_MODE:-}" ] && { export G2_NUDGE_LOG=$RUN/nudge G2_MODULE=g2_nudge.entry; mkdir -p $G2_NUDGE_LOG; }
  source $B/cluster/garage2_env.sh || exit 5
  V2=$B/weights/py123d/v0.2.0/ltf-base-joint64-68M/posttrain
  read -ra _ck <<< "${G2_CKPTS:-$V2/model_0.pth}"
  [ -f $(dirname ${_ck[0]})/config.yaml ] || { echo "no config.yaml next to ${_ck[0]}"; exit 5; }
  env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HOME=$RUN/garage_home OMP_NUM_THREADS=8 MPLCONFIGDIR=$TMPDIR/mpl \
      ${G2_MODULE:+PYTHONPATH=$B/src} $G2PY -m ${G2_MODULE:-py123d_garage.evaluation.alpasim.evaluate} hydra.run.dir=$RUN/garage \
      "policy_config.evaluation_checkpoint_files=[$(IFS=,; echo "${_ck[*]}")]" \
      policy_config.evaluation_sensor_rig_file=${G2_RIG:-$(dirname ${_ck[0]})/sensor_rig_nuplan.yaml} \
      host=localhost port=$ALPASIM_DRIVER_PORT ${G2_OVERRIDES:-} > $RUN/driver.log 2>&1 &
  READY="garage driver listening"
elif [ $DRIVER = imagep ]; then
# ---- driver: a py123d submission image (candidates P, Q, N), its own ENTRYPOINT command; HOME as in the image.
#      IMAGE_MODULE: the image's driver module; default garage_addons.entry if the image has our add-ons (P, Q), else
#      py123d's own py123d_garage.evaluation.alpasim.evaluate (N, py123d v0.2)
  IMG=${IMG:-$B/sandbox/p}
  if [ -n "${IMAGE_ARCHIVE:-}" ]; then
    # build the sandbox on the node's /local from a `docker save | gzip` archive (the dept fileset has no room;
    # Apptainer cannot read Docker Desktop's export gzipped, so decompress first)
    export APPTAINER_CACHEDIR=$TMPDIR/ac APPTAINER_TMPDIR=$TMPDIR/at; mkdir -p $APPTAINER_CACHEDIR $APPTAINER_TMPDIR
    gunzip -c $IMAGE_ARCHIVE > $TMPDIR/image.tar
    apptainer build --sandbox $TMPDIR/img docker-archive://$TMPDIR/image.tar > $RUN/sandbox.log 2>&1 \
      || { rm -rf $TMPDIR/img; apptainer build --sandbox $TMPDIR/img oci-archive://$TMPDIR/image.tar >> $RUN/sandbox.log 2>&1; }
    rm -f $TMPDIR/image.tar; IMG=$TMPDIR/img
    sha256sum $IMG/opt/checkpoint/* | tee $RUN/image_checkpoint.sha256
  fi
  apptainer exec --nv --cleanenv --writable-tmpfs --no-home \
      --env ALPASIM_DRIVER_HOST=localhost,ALPASIM_DRIVER_PORT=$ALPASIM_DRIVER_PORT \
      --env IMAGE_MODULE=${IMAGE_MODULE:-$([ -d $IMG/opt/addons/garage_addons ] && echo garage_addons.entry || echo py123d_garage.evaluation.alpasim.evaluate)} \
      $IMG sh -c 'export HOME=/tmp; exec python -m $IMAGE_MODULE ${PY123D_GARAGE_CONFIG} host=localhost port=$ALPASIM_DRIVER_PORT' \
      > $RUN/driver.log 2>&1 &
  READY="garage driver listening"
elif [ $DRIVER = image ]; then
# ---- driver: the submission image itself (apptainer sandbox of the docker image; its own ENV and code)
  IMG=${IMG:-$B/sandbox/wajepa-dev}
  # apptainer overrides the image HOME with the host home (read-only here) and ignores --env HOME:
  # restore the image value in the process environment
  apptainer exec --nv --cleanenv --writable-tmpfs --pwd /app --no-home \
      --env ALPASIM_DRIVER_HOST=localhost,ALPASIM_DRIVER_PORT=$ALPASIM_DRIVER_PORT \
      $IMG env HOME=/tmp/home python -m wajepa_challenge.driver > $RUN/driver.log 2>&1 &
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
         WAJEPA_CHECKPOINT=$B/weights/wa-jepa/model_state_dict.pt \
         WAJEPA_GTRS_CHECKPOINT=$B/weights/simscale/gtrs_dense_resnet_sim_reward_navhard.ckpt \
         WAJEPA_GTRS_VOCAB=$B/weights/simscale/navsim_16384.npy
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
SCENES_FROM=${SCENES_FROM:-$B/runs/scenes_shard001}
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
       "runtime.endpoints.driver.n_concurrent_rollouts=$ROLLOUTS $SEL ${EXTRA_OVERRIDES:-}"
} > $RUN/wizard.sh
# a node-local track root (LOCAL_PART, LOCAL_CACHE): the wizard checks that it exists, so bind it
apptainer exec -B $B $([ "${NUPLAN_ROOT#$TMPDIR}" != "$NUPLAN_ROOT" ] && echo -B $NUPLAN_ROOT) $([ -n "$ASSET_BIND" ] && [ "${ASSET_BIND#$TMPDIR}" != "$ASSET_BIND" ] && echo -B $ASSET_BIND) $SIF bash $RUN/wizard.sh > $RUN/wizard.log 2>&1 || { tail -40 $RUN/wizard.log; exit 1; }
apptainer exec -B $B $SIF /repo/.venv/bin/python -c "import yaml,json; json.dump(yaml.safe_load(open('$RUN/docker-compose.yaml')), open('$RUN/docker-compose.json','w'), indent=1)"
# Slurm sets TMPDIR=/local/slurm-job-N, which the containers cannot see (warp's NVRTC kernel build
# failed with 'cannot open temporary file'): use /tmp, which apptainer binds
TMPDIR=/tmp python3 $B/src/compose_apptainer.py $RUN/docker-compose.json --sif-dir $B/sandbox --repo-host $REPO \
  --logdir $RUN/svc-logs --cache-dir $B/cache/containers --timeout 3600 \
  $([ "$NUPLAN_ROOT" != $B/data/nuplan_track ] && echo --extra-bind $B/data/nuplan_track) $([ -n "$ASSET_BIND" ] && [ "${ASSET_BIND#$B/data/nuplan_track}" = "$ASSET_BIND" ] && echo --extra-bind $ASSET_BIND)   # symlink targets (our nuplan_test, navtest/configs); renderer start can exceed 30 min (ins038/039, 2026-10-02)
RC=$?
echo "runtime exit $RC"
python3 $B/src/tools/summarize_run.py $RUN
[ -n "$SCENES_FROM" ] && python3 $B/src/tools/compare_runs.py $SCENES_FROM $RUN
echo "driver (pid $DRV) peak GPU memory: $(grep "^$DRV," $RUN/gpu_mem.log | sort -t, -k2 -n | tail -1)"
grep "inference=\|closed session" $RUN/driver.log | tail -3
# keep the audit trail, drop the camera JPEG bytes (src/analysis/slim_asl.py; verified before deleting originals)
apptainer exec -B $B $SIF env PYTHONDONTWRITEBYTECODE=1 /repo/.venv/bin/python $B/src/analysis/slim_asl.py --delete $RUN | tail -1
exit $RC
