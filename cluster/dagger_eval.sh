#!/bin/bash
# Closed-loop eval of DAgger fine-tunes on the 7 fresh nuPlan parts (100 scenes each, the same scenes as the plain-W1
# baseline runs nuplan_garage2_w1fresh<part>_0_*), one job per part running every candidate in turn on one GPU.
# Usage (login node, submits only): bash cluster/dagger_eval.sh NAME=dir [NAME=dir ...]
#   dir = runs/dagger_models/<x> holding model_1.pth + config.yaml + sensor rigs (train.py output).
source /etc/profile
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
EXC=ins058,ins085,ins095,ins040,ins084,ins082,ins037,ins038,ins057,ins063,ins059,ins061
VARS=""; EXP=""
for kv in "$@"; do n=${kv%%=*}; d=${kv#*=}; VARS="$VARS $n"; EXP="$EXP,CKPTS_$n=$d/model_1.pth"; done
VARS=${VARS# }
for p in 002 004 006 008 009 012 015; do
  sbatch --parsable -t 03:00:00 --exclude=$EXC \
    --export=ALL,DRIVER=garage2,TAG=dgfresh${p}_,LOCAL_PART=$p,NSCENES=100,VARIANTS="$VARS"$EXP \
    $B/cluster/sim_nuplan_multi.sbatch
done
