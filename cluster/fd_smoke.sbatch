#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_fdsmoke
#SBATCH --gres=gpu:A6000:1
#SBATCH -c 8
#SBATCH --mem=64G
#SBATCH -t 01:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/fd_smoke_%j.out
# Builds the FlashDrive env and checks the stack imports and its CUDA pieces work on this node: torch/vllm versions,
# the paroquant rotation kernel (JIT build), a Marlin W4A8 linear on random weights. No model weights needed.
source /etc/profile
set -xo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
source $B/cluster/fd_env.sh || exit 5
nvidia-smi --query-gpu=name,driver_version --format=csv,noheader
which nvcc gcc; nvcc --version | tail -2; gcc --version | head -1
export HOME=$TMPDIR TORCH_EXTENSIONS_DIR=$TMPDIR/torch_ext
$FDPY - <<'PY'
import torch, transformers, vllm
print("torch", torch.__version__, "cuda", torch.version.cuda, "transformers", transformers.__version__, "vllm", vllm.__version__)
print("gpu", torch.cuda.get_device_name(), torch.cuda.get_device_capability())
import alpamayo1_5, alpamayo_r1; print("alpamayo packages ok")
import flashdrive; print("flashdrive import ok")
import paroquant.kernels.cuda; print("paroquant rotation kernel ok:", hasattr(torch.ops.rotation, "rotate"))
from flashdrive.quantization import Rotation
r = Rotation(256).cuda(); x = torch.randn(4, 256, device="cuda", dtype=torch.float16)
print("rotation identity max err", float((r(x) - x).abs().max()))
PY
