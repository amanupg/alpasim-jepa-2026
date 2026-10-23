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
         einops accelerate hydra-core omegaconf av pillow safetensors hf-xet physical-ai-av==0.2.0 ninja colorlog \
         nvidia-cuda-nvcc-cu12==12.8.93 \
    && ~/.local/bin/uv pip install -q -p $FDENV/bin/python --no-deps "alpamayo_r1 @ git+https://github.com/NVlabs/alpamayo" \
    && echo "$NR/ext/alpamayo1.5/src" > $($FDENV/bin/python -c 'import site; print(site.getsitepackages()[0])')/alpamayo1_5_src.pth \
    && echo "$B/ext/flashdrive" > $($FDENV/bin/python -c 'import site; print(site.getsitepackages()[0])')/flashdrive_src.pth \
    || { echo "fdenv build failed"; return 5 2>/dev/null || exit 5; }
  echo "fdenv built on node-local $FDENV in $(( $(date +%s) - t0 )) s"
fi
export FDPY=$FDENV/bin/python
# CUDA_HOME for paroquant's JIT rotation kernel (the cluster's cuda module has no nvcc on compute nodes): NVIDIA's pip
# packages assembled as a toolkit tree: nvcc + nvvm from cuda_nvcc, headers from every nvidia/*/include, libcudart.
SP=$($FDPY -c 'import site; print(site.getsitepackages()[0])')/nvidia
CH=$_LOC/cudahome
if [ ! -x $CH/bin/nvcc ]; then
  mkdir -p $CH/include $CH/lib64
  cp -rs $SP/cuda_nvcc/. $CH/ 2>/dev/null
  for inc in $SP/*/include; do cp -rs --remove-destination $inc/. $CH/include/ 2>/dev/null; done
  for so in $SP/cuda_runtime/lib/*; do ln -sf $so $CH/lib64/; done
  ln -sf $(ls $SP/cuda_runtime/lib/libcudart.so.* | head -1) $CH/lib64/libcudart.so
fi
export CUDA_HOME=$CH PATH=$CH/bin:$PATH
module load gcc/11.4.0 2>/dev/null
