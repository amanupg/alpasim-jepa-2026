#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_audit
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 00:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/route_audit_%j.out
# Drive-command audit on logged rollouts (alpasim-base python, read-only sandbox).
source /etc/profile
module load apptainer/1.4.5
A=/insomnia001/depts/edu/users/au2327/alpasim; B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
apptainer exec -B $A:$A:ro -B $B $A/sandbox/alpasim-base env PYTHONDONTWRITEBYTECODE=1 \
  /repo/.venv/bin/python $B/src/analysis/route_audit.py $B/runs/route_audit.json \
  $B/runs/nuplan_wajepa_v1_12994594 $B/runs/nuplan_wajepa_shard010_12994803 $B/runs/nuplan_wajepa_s005_13062857
