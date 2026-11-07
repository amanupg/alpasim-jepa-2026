# Source from a job script: builds the py123d_garage v0.2.2 driver env on node-local disk and exports G2PY.
# Same package set as the N submission image: py123d_garage's pyproject (torch 2.8 cu128) + the alpasim extra, the
# package itself from a node-local copy of ext/py123d_garage_v2 (building in the shared tree raced between jobs), and alpasim_grpc 0.54.0 built from NVlabs/alpasim e2e_challenge @ e121e59.
B=${B:-/insomnia001/depts/edu/users/au2327/alpasim-jepa}
_LOC=${TMPDIR:-/tmp/$USER-$SLURM_JOB_ID}
export UV_CACHE_DIR=$B/cache/uv UV_PYTHON_INSTALL_DIR=$B/cache/uvpython UV_LINK_MODE=copy UV_NO_CONFIG=1
G2ENV=$_LOC/g2env
UV=/insomnia001/home/au2327/.local/bin/uv    # absolute: jobs may set HOME elsewhere before sourcing this
# Packed env (2026-11-06): building copies ~100k small files from the GPFS uv cache, which took 42-53 min during a
# small-file slowdown (7 min before). One build is packed into a single tar (cluster/pack_g2env.sbatch) and later
# jobs extract it node-local. Jobs only run `$G2PY -m ...`, so the venv's absolute console-script shebangs don't matter.
G2TAR=$B/cache/g2env_v1_$(md5sum < $B/ext/py123d_garage_v2/pyproject.toml | cut -c1-8).tar
if [ ! -x $G2ENV/bin/python ] && [ -s $G2TAR ]; then
  t0=$(date +%s); mkdir -p $G2ENV
  if tar -xf $G2TAR -C $G2ENV && $G2ENV/bin/python -c 'import torch, py123d_garage, alpasim_grpc' 2>/dev/null; then
    echo "g2env extracted from $(basename $G2TAR) in $(( $(date +%s) - t0 )) s"
  else
    echo "g2env tar unusable, building"; rm -rf $G2ENV
  fi
fi
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
  if [ "${G2_PACK:-0}" = 1 ] && [ ! -s $G2TAR ]; then      # one big file on GPFS, written then renamed
    tar -cf $G2TAR.tmp.$$ -C $G2ENV . && mv $G2TAR.tmp.$$ $G2TAR && echo "packed $G2TAR ($(du -h $G2TAR | cut -f1))"
  fi
fi
export G2PY=$G2ENV/bin/python
