#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_fetchc
#SBATCH -c 2
#SBATCH --mem=4G
#SBATCH -t 01:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/fetch_nuplan_cache_%j.out
# The nuPlan track's trajdata cache and MTGS scene configs as the two public archives they ship in (OpenDriveLab HF
# dataset; the same files ../alpasim/data/nuplan_track was extracted from), kept packed in $B/data so sim jobs extract
# them onto the node's /local (sim_nuplan.sbatch LOCAL_CACHE) instead of reading 85k small files from the fileset.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; D=$B/data/nuplan_cache_hf; mkdir -p $D
for f in trajdata_cache/nuplan_test.tar.gz MTGS_asset/navtest/configs.tar.gz; do
  for attempt in 1 2 3; do
    # token file path only, never the token itself (Aman 2026-10-10); public dataset
    HOME=$TMPDIR/home HF_HUB_DISABLE_TELEMETRY=1 HF_XET_HIGH_PERFORMANCE=1 HF_TOKEN_PATH=/insomnia001/depts/edu/users/au2327/alpasim/.cache/hf/token \
      $B/envs/garage/bin/hf download OpenDriveLab/AlpasimChallenge2026_nuplan_track --repo-type dataset --include "$f" --local-dir $TMPDIR/dl > /dev/null && break
    sleep 60
  done
  gzip -t $TMPDIR/dl/$f
  cp $TMPDIR/dl/$f $D/$(basename $f).partial && mv $D/$(basename $f).partial $D/$(basename $f)
done
ls -la $D; sha256sum $D/*.tar.gz
