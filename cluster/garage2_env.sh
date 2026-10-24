# Source from a job script: builds the py123d_garage v0.2.2 driver env on node-local disk and exports G2PY.
# Same package set as the N submission image: py123d_garage's pyproject (torch 2.8 cu128) + the alpasim extra, the
# package itself from a node-local copy of ext/py123d_garage_v2 (building in the shared tree raced between jobs), and alpasim_grpc 0.54.0 built from NVlabs/alpasim e2e_challenge @ e121e59.
B=${B:-/insomnia001/depts/edu/users/au2327/alpasim-jepa}
_LOC=${TMPDIR:-/tmp/$USER-$SLURM_JOB_ID}
export UV_CACHE_DIR=$B/cache/uv UV_PYTHON_INSTALL_DIR=$B/cache/uvpython UV_LINK_MODE=copy UV_NO_CONFIG=1
G2ENV=$_LOC/g2env
UV=/insomnia001/home/au2327/.local/bin/uv    # absolute: jobs may set HOME elsewhere before sourcing this
if [ ! -x $G2ENV/bin/python ]; then
  t0=$(date +%s)
  $UV venv -q -p 3.12 $G2ENV \
    && $UV pip install -q -p $G2ENV/bin/python -r $B/ext/py123d_garage_v2/pyproject.toml --extra alpasim --extra train \
    && rm -rf $_LOC/py123d_src && cp -r $B/ext/py123d_garage_v2 $_LOC/py123d_src \
    && $UV pip install -q -p $G2ENV/bin/python --no-deps $_LOC/py123d_src \
    && $UV pip install -q -p $G2ENV/bin/python --find-links $B/container/wheels_e121e59 alpasim-grpc \
    && $UV pip install -q -p $G2ENV/bin/python "huggingface_hub[hf_xet]" wandb==0.30.0 protobuf==7.36.2 \
    || { echo "g2env build failed"; return 5 2>/dev/null || exit 5; }
  echo "g2env built on node-local $G2ENV in $(( $(date +%s) - t0 )) s: $($G2ENV/bin/python -c 'import torch, py123d_garage, alpasim_grpc; print("torch", torch.__version__, "alpasim_grpc", alpasim_grpc.__version__)')"
fi
export G2PY=$G2ENV/bin/python
