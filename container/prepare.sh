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
du -sh $S/*
