#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_dedupe
#SBATCH -c 8
#SBATCH --mem=8G
#SBATCH -t 03:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/dedupe_hash_%j.out
# Read-only duplicate check (Aman 2026-10-18): sha256 of every file under SUBS in the alpasim and alpasim-jepa copies
# of the nuPlan track data, then a per-subdir summary (identical / differing / only on one side). Deletes nothing.
source /etc/profile
set -eo pipefail
U=/insomnia001/depts/edu/users/au2327
SUBS=${SUBS:-"nuplan_test navtest/configs"}
REUSE=${REUSE:-}     # a previous dedupe_<job> dir: hash files found there (non-empty) are reused
OUT=$U/alpasim-jepa/logs/dedupe_$SLURM_JOB_ID; mkdir -p $OUT
for sub in $SUBS; do
  tag=$(echo $sub | tr / _)
  for side in alpasim alpasim-jepa; do
    if [ -n "$REUSE" ] && [ -s $REUSE/${side}_$tag.sha ]; then cp $REUSE/${side}_$tag.sha $OUT/; echo "reused $side $sub"; continue; fi
    (cd $U/$side/data/nuplan_track/$sub && find . -type f -print0 | xargs -0 -P 8 -n 200 sha256sum | sort -k2) > $OUT/${side}_$tag.sha
  done
  a=$OUT/alpasim_$tag.sha; j=$OUT/alpasim-jepa_$tag.sha
  echo "== $sub: alpasim $(wc -l < $a) files, alpasim-jepa $(wc -l < $j) files"
  echo "identical (same path + hash): $(comm -12 $a $j | wc -l)"
  echo "path on both sides, hash differs: $(join -1 2 -2 2 <(sort -k2 $a) <(sort -k2 $j) | awk '$2 != $3' | wc -l)"
  echo "only alpasim: $(comm -23 <(awk '{print $2}' $a) <(awk '{print $2}' $j) | wc -l), only alpasim-jepa: $(comm -13 <(awk '{print $2}' $a) <(awk '{print $2}' $j) | wc -l)"
  echo "size (alpasim-jepa copy): $(du -s --block-size=1M $U/alpasim-jepa/data/nuplan_track/$sub | cut -f1) MB"
done
