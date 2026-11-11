#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_nrfetch
#SBATCH -c 16
#SBATCH --mem=64G
#SBATCH -t 03:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/nurec_fetch_%j.out
# NuRec eval setup (2026-11-10): rebuild what the PAI thread had in the deleted ../alpasim folder.
#   PART=image: pull the NRE renderer (nvcr.io/nvidia/nre/nre-ga:26.04, anonymous pull) into $B/sif (built on /local).
#   PART=scenes: download the 441 nurec_curated_val scenes into $B/data/fs/nre-artifacts via the wizard
#     (run_method=NONE). HF auth: the token file in $B/.cache/hf is read in place by huggingface_hub (HF_HOME),
#     never printed or passed on a command line.
source /etc/profile
module load apptainer/1.4.5
set -x
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; SIF=$B/sandbox/alpasim-base
mkdir -p $B/sif
if [ "$PART" = image ]; then
  # 2026-11-11: pulling with the temp dir on the dept fileset spent > 6 h in unpack/mksquashfs (millions of small
  # files on GPFS) and timed out. Build on the node's /local and copy only the single .sif file to the fileset; the
  # NuRec jobs unpack it to a sandbox on their own /local (cluster/sim_nurec.sbatch).
  export APPTAINER_TMPDIR=$TMPDIR/at APPTAINER_CACHEDIR=$TMPDIR/ac; mkdir -p $APPTAINER_TMPDIR $APPTAINER_CACHEDIR
  df -h $TMPDIR
  [ -s $B/sif/nre-ga_26.04.sif ] || { time apptainer pull $TMPDIR/nre.sif docker://nvcr.io/nvidia/nre/nre-ga:26.04 \
    && cp $TMPDIR/nre.sif $B/sif/nre-ga_26.04.sif.tmp && mv $B/sif/nre-ga_26.04.sif.tmp $B/sif/nre-ga_26.04.sif; }
  ls -la $B/sif; sha256sum $B/sif/nre-ga_26.04.sif
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
