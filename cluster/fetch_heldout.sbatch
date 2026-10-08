#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_heldout
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 04:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/fetch_heldout_%j.out
# A fresh held-out scene set: fetch MTGS asset part P (public OpenDriveLab nuPlan track) and record the scenes it
# adds as runs/scenes_shard<P>/{ids,scene_ids}.txt. Run parts one after another (the "new" set is a directory diff).
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; D=$B/runs/scenes_shard$P; mkdir -p $D
ls $B/data/nuplan_track/navtest/assets > $D/assets_before.txt
SHARDS=$P bash $B/cluster/fetch_nuplan_shard.sbatch
ls $B/data/nuplan_track/navtest/assets | grep -vxFf $D/assets_before.txt > $D/ids.txt
echo "part $P: $(wc -l < $D/ids.txt) new scenes"; cut -d_ -f1-2 $D/ids.txt | sort | uniq -c
sed "s/.*/'&'/" $D/ids.txt | paste -sd, - > $D/scene_ids.txt
