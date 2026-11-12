#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_nupm
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|l40|h100   # nuPlan MTGS renderer pins TORCH_CUDA_ARCH_LIST=8.9;9.0 (L40S/L40/H100)
#SBATCH -c 12
#SBATCH --mem=120G
#SBATCH -t 02:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/sim_nuplan_multi_%j.out
# Several driver variants on the same scenes, one after another on ONE GPU, so they are paired on the same hardware
# (and wait in the queue once). Each variant is a full cluster/sim_nuplan.sbatch run (run dir
# runs/nuplan_<DRIVER>_<TAG><variant>_<jobid>, own node-local scratch). VARIANTS: space-separated, "0" = plain driver,
# A/B = G2_NUDGE_MODE (src/g2_nudge), other names = plain driver with CKPTS_<name> if set. All other settings (DRIVER, G2_CKPTS, SCENES_FROM, TAG prefix) via --export.
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
G2_CKPTS0=${G2_CKPTS:-}   # the job-wide checkpoint list, restored for variants without their own CKPTS_<name>
BASE_TMP=${TMPDIR:?}
for M in ${VARIANTS:-0 A B}; do
  mkdir -p $BASE_TMP/v$M
  case $M in A|B) NM=$M;; *) NM=;; esac
  # CKPTS_<variant>="<file> [...]" (exported) overrides G2_CKPTS for that variant, e.g. CKPTS_E3 = a seed ensemble
  CKV=CKPTS_$M; CK=${!CKV:-${G2_CKPTS0:-}}
  echo "=== variant $M ($(date)) ckpts: ${CK:-default}"
  if [ -n "$CK" ]; then export G2_CKPTS="$CK"; fi
  # ENV_<variant>="K=V ..." (exported): extra environment for that variant only, e.g. G2_MODULE=g2_slow.entry G2_SLOW_F=0.9
  EV=ENV_$M; read -ra XE <<< "${!EV:-}"; echo "    extra env: ${XE[*]:-none}"
  env TMPDIR=$BASE_TMP/v$M TAG=${TAG:-multi}$M G2_NUDGE_MODE=$NM "${XE[@]}" bash $B/cluster/sim_nuplan.sbatch
  echo "=== variant $M exit $?"
  rm -rf $BASE_TMP/v$M
  sleep 30   # let the previous run's services release their ports
done
