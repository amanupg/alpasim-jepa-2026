# Prebuilds paroquant 0.1.15's rotation kernel (registers torch.ops.rotation.rotate via TORCH_LIBRARY) for torch 2.9.1 /
# CUDA 12.8 / Python 3.12, for A6000 (8.6), L40S (8.9), H100 (9.0) and A100 (8.0). No GPU needed to compile.
FROM nvidia/cuda:12.8.1-devel-ubuntu24.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends python3.12 python3.12-venv python3.12-dev ninja-build g++ && rm -rf /var/lib/apt/lists/*
RUN python3.12 -m venv /v && /v/bin/pip install -q torch==2.9.1 numpy ninja && /v/bin/pip install -q --no-deps paroquant==0.1.15
ENV TORCH_CUDA_ARCH_LIST="8.0;8.6;8.9;9.0" MAX_JOBS=4
RUN mkdir -p /out && cd /v/lib/python3.12/site-packages/paroquant/kernels/cuda && \
    /v/bin/python -c "from torch.utils.cpp_extension import load; import shutil; \
load(name='paroquant_rotation', sources=['pybind.cpp','rotation.cu'], build_directory='/out', verbose=True, \
extra_cuda_cflags=['-O3','-std=c++17','-U__CUDA_NO_HALF_OPERATORS__','-U__CUDA_NO_HALF_CONVERSIONS__','-U__CUDA_NO_BFLOAT16_OPERATORS__','-U__CUDA_NO_BFLOAT16_CONVERSIONS__','--expt-relaxed-constexpr','--expt-extended-lambda','--use_fast_math'], \
extra_cflags=['-O2','-std=c++17'])" 2>&1 | tail -5; ls -la /out; sha256sum /out/paroquant_rotation.so
