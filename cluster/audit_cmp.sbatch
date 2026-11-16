#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_audit
#SBATCH -c 2
#SBATCH --mem=8G
#SBATCH -t 00:20:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/audit_cmp_%j.out
source /etc/profile; module load apptainer/1.4.5
A=/insomnia001/depts/edu/users/au2327/alpasim; B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; R=$B/runs/nuplan_wajepa_s005_13062857
for n in rollout.asl rollout.slim.asl; do
  apptainer exec -B $A:$A:ro -B $B $A/sandbox/alpasim-base env PYTHONDONTWRITEBYTECODE=1 ASL_NAME=$n \
    /repo/.venv/bin/python $B/src/analysis/route_audit.py /tmp/audit_$n.json $R | tail -2
  md5sum /tmp/audit_$n.json
done
