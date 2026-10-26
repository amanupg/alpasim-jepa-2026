#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_cltrain
#SBATCH --gres=gpu:A6000:1
#SBATCH --ntasks-per-node=1
#SBATCH -c 8
#SBATCH --mem=96G
#SBATCH -t 06:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/cl_train_%j.out
# Closed-loop (DAgger-style) fine-tune of py123d v0.2.0's planning decoder on records from src/g2_addons/collect.py
# with recovery labels (src/closed_loop/labels.py); backbone and other heads frozen (src/closed_loop/train_decoder.py).
#   CL_DATA=<dir>[:<dir>...] (capture dirs), INIT (default released joint64 posttrain model_0), CL_EPOCHS, CL_LR,
#   CL_BATCH, CL_VAL_FRAC, CL_MAX_RECORDS; output $RUN/model_cl.pth
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
RUN=${RUN_DIR:-$B/runs/cltrain${TAG:+_$TAG}_$SLURM_JOB_ID}; mkdir -p $RUN
source $B/cluster/garage2_env.sh
V2=$B/weights/py123d/v0.2.0/ltf-base-joint64-68M/posttrain
INIT=${INIT:-$V2/model_0.pth}
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
env PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1 HF_HUB_OFFLINE=1 HOME=$RUN/home OMP_NUM_THREADS=8 MPLCONFIGDIR=$TMPDIR/mpl \
    PYTHONPATH=$B/src CL_OUT=$RUN/model_cl.pth \
    $G2PY -m closed_loop.train_decoder hydra.run.dir=$RUN/hydra \
    "policy_config.evaluation_checkpoint_files=[$INIT]" \
    policy_config.evaluation_sensor_rig_file=$(dirname $INIT)/sensor_rig_nuplan.yaml device=cuda 2>&1 | tee $RUN/train.log
cp $(dirname $INIT)/config.yaml $(dirname $INIT)/sensor_rig_nuplan.yaml $RUN/ 2>/dev/null || cp $V2/config.yaml $V2/sensor_rig_nuplan.yaml $RUN/
ls -la $RUN
