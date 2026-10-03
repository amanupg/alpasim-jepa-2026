#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_slim
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 06:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/slim_asl_%j.out
# Slim rollout logs (src/analysis/slim_asl.py). RUNS="dir ..." (default: all of runs/*), DELETE=1 removes verified originals.
source /etc/profile
module load apptainer/1.4.5
A=/insomnia001/depts/edu/users/au2327/alpasim; B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
RUNS=${RUNS:-$(ls -d $B/runs/nuplan_* $B/runs/pai_* 2>/dev/null)}
apptainer exec -B $A:$A:ro -B $B $A/sandbox/alpasim-base env PYTHONDONTWRITEBYTECODE=1 \
  /repo/.venv/bin/python $B/src/analysis/slim_asl.py ${DELETE:+--delete} $RUNS
