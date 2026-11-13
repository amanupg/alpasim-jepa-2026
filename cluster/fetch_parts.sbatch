#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_fetchp
#SBATCH -c 8
#SBATCH --mem=16G
#SBATCH -t 06:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/fetch_parts_%j.out
# Fresh MTGS asset parts (public OpenDriveLab nuPlan-track data) for LOCAL_PART runs, fetched in parallel to the
# fileset once, so each nuPlan job does not spend ~2 h downloading at ~3 MB/s (2026-11-12). PARTS="004 006 ...".
# Used by cluster/sim_nuplan.sbatch when $B/data/mtgs_parts/part<NNN>.tar.gz exists. Token file path only.
source /etc/profile
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
D=$B/data/mtgs_parts; mkdir -p $D
for P in $PARTS; do
  ( [ -s $D/part$P.tar.gz ] && exit 0
    for attempt in 1 2 3; do
      HOME=$TMPDIR/home_$P HF_HUB_DISABLE_TELEMETRY=1 HF_XET_HIGH_PERFORMANCE=1 HF_TOKEN_PATH=$B/.cache/hf/token $B/envs/garage/bin/hf download OpenDriveLab/AlpasimChallenge2026_nuplan_track \
        --repo-type dataset --include "MTGS_asset/navtest/assets/part$P.tar.gz" --local-dir $TMPDIR/dl_$P > /dev/null 2>&1 && break
      sleep 60
    done
    f=$TMPDIR/dl_$P/MTGS_asset/navtest/assets/part$P.tar.gz
    gzip -t $f && mv $f $D/part$P.tar.gz.tmp && mv $D/part$P.tar.gz.tmp $D/part$P.tar.gz && echo "part $P ok $(du -h $D/part$P.tar.gz | cut -f1)" || echo "part $P FAILED"
  ) &
done
wait
