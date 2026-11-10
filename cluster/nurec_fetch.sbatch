#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_nrfetch
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 06:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/nurec_fetch_%j.out
# NuRec eval setup (2026-11-10): rebuild what the PAI thread had in the deleted ../alpasim folder.
#   PART=image: pull the NRE renderer (nvcr.io/nvidia/nre/nre-ga:26.04, anonymous pull) and unpack it to a sandbox.
#   PART=scenes: download the 441 nurec_curated_val scenes into $B/data/fs/nre-artifacts via the wizard
#     (run_method=NONE). HF auth: the token file in $B/.cache/hf is read in place by huggingface_hub (HF_HOME),
#     never printed or passed on a command line.
source /etc/profile
module load apptainer/1.4.5
set -x
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; SIF=$B/sandbox/alpasim-base
export APPTAINER_TMPDIR=$B/tmp/apptainer; mkdir -p $APPTAINER_TMPDIR $B/sif
if [ "$PART" = image ]; then
  [ -s $B/sif/nre-ga_26.04.sif ] || { apptainer pull $B/sif/nre-ga_26.04.sif.tmp docker://nvcr.io/nvidia/nre/nre-ga:26.04 && mv $B/sif/nre-ga_26.04.sif.tmp $B/sif/nre-ga_26.04.sif; }
  [ -d $B/sandbox/nre-ga_26.04/usr ] || { rm -rf $B/sandbox/nre-ga_26.04.tmp; apptainer build --sandbox $B/sandbox/nre-ga_26.04.tmp $B/sif/nre-ga_26.04.sif && mv $B/sandbox/nre-ga_26.04.tmp $B/sandbox/nre-ga_26.04; }
  du -sh $B/sif/nre-ga_26.04.sif $B/sandbox/nre-ga_26.04
fi
if [ "$PART" = scenes ]; then
  RUN=$B/runs/nurec_fetch_$SLURM_JOB_ID; mkdir -p $RUN
  REPO=$B/ext/alpasim_sim
  {
    echo "cd $RUN"
    echo "export HF_HOME=$B/.cache/hf HF_XET_HIGH_PERFORMANCE=1 HF_HUB_DISABLE_TELEMETRY=1"
    echo "exec /repo/.venv/bin/alpasim_wizard +e2e_challenge=dev +nurec_scenes=curated_val scenes.limit_to_first_n=${NSCENES:-0}" \
         "wizard.run_method=NONE wizard.log_dir=$RUN defines.filesystem=$B/data/fs hydra.run.dir=$RUN/hydra"
  } > $RUN/wizard.sh
  time apptainer exec -B $B $SIF bash $RUN/wizard.sh > $RUN/wizard.log 2>&1; echo "wizard exit $?"
  tail -8 $RUN/wizard.log
  find $B/data/fs/nre-artifacts -name "*.usdz" | wc -l; du -shL $B/data/fs/nre-artifacts
fi
