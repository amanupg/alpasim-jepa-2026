#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_pack
#SBATCH -c 4
#SBATCH --mem=8G
#SBATCH -t 06:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/pack_nuplan_cache_%j.out
# One tar of the nuPlan track's trajdata cache (nuplan_test, ~12k scene dirs, 85k small files) + navtest/configs, read
# once from ../alpasim (read-only) so sim jobs can stream it onto the node's /local instead of scanning 85k GPFS files
# per run (2026-10-26: the renderer's UnifiedDataset scan went from 4.5 min to > 30 min under fileset load).
source /etc/profile
set -eo pipefail
A=/insomnia001/depts/edu/users/au2327/alpasim/data/nuplan_track; B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
OUT=$B/data/nuplan_cache.tar
t0=$(date +%s)
tar -cf $TMPDIR/cache.tar -C $A nuplan_test navtest/configs
echo "packed in $(( $(date +%s) - t0 )) s: $(ls -la $TMPDIR/cache.tar)"
tar -tf $TMPDIR/cache.tar | awk -F/ '$1=="nuplan_test" && NF>=3 {print $2}' | sort -u | wc -l
cp $TMPDIR/cache.tar $OUT.partial && mv $OUT.partial $OUT
ls -la $OUT; echo "total $(( $(date +%s) - t0 )) s"
