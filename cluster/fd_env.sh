# Source from a job script: builds the FlashDrive driver env on node-local disk and exports FDPY.
# Python 3.12, vllm 0.16.0 (pulls torch 2.9.1 cu128, the FlashDrive pin), paroquant 0.1.15, transformers 4.57.1,
# alpamayo_r1 (FlashDrive imports it) from GitHub; alpamayo1_5 from nureasoning/ext/alpamayo1.5/src via a .pth file,
# the same source v5 uses (read-only). uv's wheel cache lives in alpasim-jepa/cache/uv; the env itself is node-local.
B=${B:-/insomnia001/depts/edu/users/au2327/alpasim-jepa}
NR=${NR:-/insomnia001/depts/edu/users/au2327/nureasoning}
_LOC=${TMPDIR:-/tmp/$USER-$SLURM_JOB_ID}
export UV_CACHE_DIR=$B/cache/uv UV_PYTHON_INSTALL_DIR=$B/cache/uvpython UV_LINK_MODE=copy UV_NO_CONFIG=1
FDENV=$_LOC/fdenv
if [ ! -x $FDENV/bin/python ]; then
  t0=$(date +%s)
  ~/.local/bin/uv venv -q -p 3.12 $FDENV \
    && ~/.local/bin/uv pip install -q -p $FDENV/bin/python vllm==0.16.0 paroquant==0.1.15 transformers==4.57.1 \
         einops accelerate hydra-core omegaconf av pillow safetensors hf-xet physical-ai-av==0.2.0 ninja \
    && ~/.local/bin/uv pip install -q -p $FDENV/bin/python --no-deps "alpamayo_r1 @ git+https://github.com/NVlabs/alpamayo" \
    && echo "$NR/ext/alpamayo1.5/src" > $($FDENV/bin/python -c 'import site; print(site.getsitepackages()[0])')/alpamayo1_5_src.pth \
    && echo "$B/ext/flashdrive" > $($FDENV/bin/python -c 'import site; print(site.getsitepackages()[0])')/flashdrive_src.pth \
    || { echo "fdenv build failed"; return 5 2>/dev/null || exit 5; }
  echo "fdenv built on node-local $FDENV in $(( $(date +%s) - t0 )) s"
fi
export FDPY=$FDENV/bin/python
