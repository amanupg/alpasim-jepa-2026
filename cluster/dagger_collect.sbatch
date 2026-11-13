#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_dag
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s|l40|h100
#SBATCH -c 12
#SBATCH --mem=120G
#SBATCH -t 01:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/dagger_collect_%j.out
# DAgger data collection (src/g2_dagger/entry.py): a driver (default W1) drives training scenes with the human trajectory
# sent to it (local only) and saves one sample per plan to data/dagger/<TAG>. SCENES_FROM=<dir with scene_ids.txt>.
# NOISE (default 0), SEED, CKPT (default W1 model_1.pth).
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
W1=$B/weights/py123d/v0.2.0/ltf-base-waypoints-68M/posttrain/model_1.pth
export DRIVER=garage2 G2_CKPTS=${CKPT:-$W1} G2_MODULE=g2_dagger.entry
export G2_DAGGER_DIR=$B/data/dagger/${TAG:?} G2_DAGGER_NOISE=${NOISE:-0} G2_DAGGER_SEED=${SEED:-0}
export EXTRA_OVERRIDES="runtime.simulation_config.send_recording_ground_truth=true ${EXTRA_OVERRIDES:-}"
mkdir -p $G2_DAGGER_DIR
bash $B/cluster/sim_nuplan.sbatch
echo "samples: $(ls $G2_DAGGER_DIR | wc -l)"
