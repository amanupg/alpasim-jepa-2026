#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_fetch
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 04:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/fetch_nuplan_%j.out
# Held-out nuPlan scenes for alpasim-jepa: our own copy of the public OpenDriveLab nuPlan-track data
# (trajdata cache + scene configs + the asset shards in SHARDS), streamed straight into tar.
# Public dataset, no auth. Kept apart from the AlpaSim data folder, which is read-only here.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
ROOT=$B/data/nuplan_track; mkdir -p $ROOT/.done
export PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1
url() { echo "https://huggingface.co/datasets/OpenDriveLab/AlpasimChallenge2026_nuplan_track/resolve/main/$1"; }
get() {
  local f=$1 tag=$(basename $1)
  [ -e $ROOT/.done/$tag ] && { echo "have $f"; return; }
  echo "$(date -u +%T) fetching $f"
  curl -sSfL --retry 5 "$(url $f)" | tar -xz -C $ROOT && touch $ROOT/.done/$tag
  echo "$(date -u +%T) done $f"; du -sh $ROOT
}
get trajdata_cache/nuplan_test.tar.gz
get MTGS_asset/navtest/configs.tar.gz
for s in ${SHARDS:-010}; do get MTGS_asset/navtest/assets/part$s.tar.gz; done
ls $ROOT $ROOT/navtest
echo "assets $(ls $ROOT/navtest/assets | wc -l), logs: $(ls $ROOT/navtest/assets | cut -d_ -f1-2 | sort | uniq -c | tr '\n' ' ')"
