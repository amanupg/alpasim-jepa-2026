#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_gtrain
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 01:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/setup_garage_train_%j.out
# Training env for py123d_garage v0.1.1 (extra "train": lightning, lmdb, wandb, huggingface-hub), separate from
# envs/garage so the evaluation env used by the simulator runs never changes.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; UV=$HOME/.local/bin/uv
export UV_CACHE_DIR=$B/cache/uv UV_PYTHON_INSTALL_DIR=$B/cache/uvpython PYTHONNOUSERSITE=1
G=$B/ext/py123d_garage; E=$B/envs/garage-train
git -C $G log -1 --format="garage %h %cd"
$UV venv -q --clear --python 3.12 $E
$UV pip install -q --python $E/bin/python -r $G/pyproject.toml --extra train
$UV pip install -q --python $E/bin/python --no-deps $G
$E/bin/python -c "import torch, lightning, lmdb, numpy, py123d, py123d_garage; print('torch', torch.__version__, 'lightning', lightning.__version__, 'numpy', numpy.__version__, 'cuda build', torch.version.cuda)"
