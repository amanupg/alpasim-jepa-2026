#!/usr/bin/env bash
# Stage build inputs that are not kept in git (all public, pinned):
#   - WA-JEPA inference code @ bec2966 (Apache-2.0): models/, training/, utils/, third_party/, configs/, LICENSE
#   - WA-JEPA weights, HF AFARI-Research/WA-JEPA @ 15c0770e, sha256-checked
#   - alpasim_grpc from NVlabs/alpasim e2e_challenge @ 2023534 (src/grpc)
set -euo pipefail
cd "$(dirname "$0")/.."
WA_COMMIT=bec2966; UP_COMMIT=2023534; HF_REV=15c0770e
WA_SHA=e1d3be013de7dbaa5a6c30925a0d2f91e6ce1a6b17a75ca73fe01a1abe6d6408
S=container/assets; mkdir -p $S
[ -d ext/WA-JEPA ] || git clone -q https://github.com/AFARI-Research/WA-JEPA.git ext/WA-JEPA
rm -rf $S/wa_jepa_code && mkdir -p $S/wa_jepa_code
git -C ext/WA-JEPA archive $WA_COMMIT models training utils third_party configs LICENSE | tar -x -C $S/wa_jepa_code
[ -d ext/alpasim-upstream ] || git clone -q --filter=blob:none --no-checkout --branch e2e_challenge \
  https://github.com/NVlabs/alpasim.git ext/alpasim-upstream
rm -rf $S/alpasim_grpc && mkdir -p $S/alpasim_grpc
git -C ext/alpasim-upstream archive $UP_COMMIT src/grpc | tar -x --strip-components=2 -C $S/alpasim_grpc
W=$S/wa_jepa/model_state_dict.pt; mkdir -p $(dirname $W)
if ! echo "$WA_SHA  $W" | shasum -a 256 -c - >/dev/null 2>&1; then
  curl -sSfL --retry 5 -o $W.part "https://huggingface.co/AFARI-Research/WA-JEPA/resolve/$HF_REV/model_state_dict.pt"
  mv $W.part $W
fi
echo "$WA_SHA  $W" | shasum -a 256 -c -
# GTRS-Dense judge (organisers' SimScale sample): checkpoint from HF OpenDriveLab/SimScale (Apache-2.0),
# vocabulary = the git-lfs object of NVlabs/alpasim @ 2023534 (the checkout holds a pointer)
G=$S/gtrs; mkdir -p $G
get() { echo "$2  $G/$1" | shasum -a 256 -c - >/dev/null 2>&1 || curl -sSfL --retry 5 -o $G/$1 "$3"; echo "$2  $G/$1" | shasum -a 256 -c -; }
get gtrs_dense_resnet_sim_reward_navhard.ckpt 8dad0395332ccd844785cbfc7c9e24cb3f8d8dbf5cb9ca7f8f8dc75478fcf409 \
  https://huggingface.co/datasets/OpenDriveLab/SimScale/resolve/main/SimScale_ckpts/GTRS_Dense/gtrs_dense_resnet_sim_reward_navhard.ckpt
get navsim_16384.npy e8c29cfc25add59ae8b64769a4554c6518878726178c0bd889fc8518ebe1261d \
  https://media.githubusercontent.com/media/NVlabs/alpasim/$UP_COMMIT/e2e_challenge/sample_submission_simscale_navsim_gtrs_dense/assets/gtrs_dense/navsim_16384.npy
du -sh $S/*
