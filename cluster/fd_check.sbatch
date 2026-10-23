#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_fdcheck
#SBATCH --gres=gpu:A6000:1
#SBATCH -c 8
#SBATCH --mem=96G
#SBATCH -t 02:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/fd_check_%j.out
# Open-loop check of the FlashDrive policy on N captured PAI plans (pai_flashdrive/check_policy.py): latency, memory,
# ADE to the recorded future; REFERENCE=1 adds the v5 forced-start path on the original bf16 weights (needs ~22 GB).
source /etc/profile
set -o pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; A=/insomnia001/depts/edu/users/au2327/alpasim
NR=/insomnia001/depts/edu/users/au2327/nureasoning
source $B/cluster/fd_env.sh || exit 5
module load cuda/12.3 2>/dev/null
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
mkdir -p $TMPDIR/cap && tar -xf $A/data/ft_capture/${CAP:-cap_c1_13609283.tar} -C $TMPDIR/cap
HUB=$NR/.cache/hf/hub
export A15_MODEL_DIR=$B/weights/flashdrive/Alpamayo-1.5-10B A15_PARO_DIR=$B/weights/flashdrive/Alpamayo-1.5-10B-PARO
export A15_REF_MODEL_DIR=$(ls -d $HUB/models--nvidia--Alpamayo-1.5-10B/snapshots/*/ | head -1)
export A15_VLM_DIR=$(ls -d $HUB/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/*/ | head -1)
export A15_PROCESSOR_DIR=$(ls -d $HUB/models--Qwen--Qwen3-VL-2B-Instruct/snapshots/*/ | head -1)
export HOME=$TMPDIR TORCH_EXTENSIONS_DIR=$TMPDIR/torch_ext HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONNOUSERSITE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True TOKENIZERS_PARALLELISM=false
mkdir -p $B/runs/fd_check
$FDPY -u $B/pai_flashdrive/check_policy.py --samples $TMPDIR/cap --n ${N:-40} $([ "${REFERENCE:-0}" = 1 ] && echo --reference) \
  --out $B/runs/fd_check/plans_$SLURM_JOB_ID.npz 2>&1 | grep -v "Warning\|warn(" | tail -40
