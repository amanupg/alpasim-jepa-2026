#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_pytrain
#SBATCH --gres=gpu:l40s:1
#SBATCH -c 16
#SBATCH --mem=120G
#SBATCH -t 04:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/py123d_train_%j.out
# py123d latent TransFuser planning posttraining on nuPlan (preset ltf_nuplan_trainval), initialised from the
# public resnet34_v0.1.0/model_0014.pth: the checkpoint README's finetuning recipe. W&B off.
#   EPOCHS (default 1), LIMIT (lightning limit_train_batches, default 1.0), BATCH (global, default 64),
#   LR (default: preset), COMPILE (default max-autotune as posttrain.sh), INIT (default the public 0014), TAG
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
export PY123D_GARAGE_DATA_ROOT=$B/data/py123d PYTHONNOUSERSITE=1 PY123D_GARAGE_RUNTIME_TYPE_CHECKING=false
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMBA_NUM_THREADS=1 NUMBA_THREADING_LAYER=workqueue
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True WANDB_MODE=disabled HOME=$B/runs/py123d_home TMPDIR=/tmp
mkdir -p $HOME
GPUS=$(nvidia-smi --list-gpus | wc -l); BATCH=${BATCH:-64}
INIT=${INIT:-$B/weights/py123d/resnet34_v0.1.0/model_0014.pth}
RUN=$B/runs/py123d_train${TAG:+_$TAG}_$SLURM_JOB_ID
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
cd $B/ext/py123d_garage
srun --kill-on-bad-exit=1 -n $GPUS $B/envs/garage/bin/python -m py123d_garage.training.train \
  training=py123d_garage.config.presets.python.training.latent_transfuser:ltf_nuplan_trainval \
  compile_mode=${COMPILE:-max-autotune} \
  hydra.run.dir=$RUN \
  policy_config.transfuser_config.planning_config.use_planning_decoder=true \
  initial_weights_file="'$INIT'" initial_weights_strict=true \
  wandb_config.enabled=false \
  lightning_trainer_config.devices=$GPUS lightning_trainer_config.num_nodes=1 \
  lightning_trainer_config.max_epochs=${EPOCHS:-1} lightning_trainer_config.limit_train_batches=${LIMIT:-1.0} \
  lightning_trainer_config.log_every_n_steps=10 \
  ${LR:+optimizer_config.learning_rate=$LR} \
  dataloader_config.batch_size=$((BATCH / GPUS)) dataloader_config.num_workers=$(( ${SLURM_CPUS_PER_TASK:-16} / GPUS )) \
  ${TRAIN_OVERRIDES:-}
ls -la $RUN | head -30
