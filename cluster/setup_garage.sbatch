#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_garage
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 01:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/setup_garage_%j.out
# py123d_garage (kesai-labs, Apache-2.0) v0.1.1 @ 288d34c + its public nuPlan/PAI checkpoint
# (HF kesai-labs/py123d_garage_pretrained_checkpoints @ 5516edd, resnet34_v0.1.0/model_0014.pth),
# in its own uv venv (python 3.12; the package pins numpy<2.3, so it cannot share a15env).
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; UV=$HOME/.local/bin/uv
export UV_CACHE_DIR=$B/cache/uv UV_PYTHON_INSTALL_DIR=$B/cache/uvpython PYTHONNOUSERSITE=1
G=$B/ext/py123d_garage
[ -d $G ] || git clone -q --branch v0.1.1 https://github.com/kesai-labs/py123d_garage.git $G
git -C $G log -1 --format="garage %h %cd"
$UV venv -q --clear --python 3.12 $B/envs/garage
$UV pip install -q --python $B/envs/garage/bin/python -r $G/pyproject.toml --extra alpasim
$UV pip install -q --python $B/envs/garage/bin/python --no-deps $G
# alpasim_grpc from our own archive of NVlabs/alpasim src/grpc @ 2023534 (container/prepare.sh), never the
# read-only AlpaSim checkout (a build could write into it)
$UV pip install -q --python $B/envs/garage/bin/python --no-deps $B/ext/alpasim_grpc
W=$B/weights/py123d; mkdir -p $W
$B/envs/garage/bin/python - <<PY
from huggingface_hub import snapshot_download
p = snapshot_download("kesai-labs/py123d_garage_pretrained_checkpoints", revision="5516eddafcfa4b622c3df59200e5b189ef328182",
                      allow_patterns=["resnet34_v0.1.0/*"], local_dir="$W", token=False)
print("checkpoint at", p)
PY
ls -la $W/resnet34_v0.1.0
$B/envs/garage/bin/python -c "import torch, numpy, py123d, py123d_garage, alpasim_grpc, grpc; print('torch', torch.__version__, 'numpy', numpy.__version__, 'py123d', getattr(py123d,'__version__','?'), 'grpc', alpasim_grpc.__version__)"
