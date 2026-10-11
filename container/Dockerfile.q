# nuPlan driver, candidate Q: py123d_garage (kesai-labs, Apache-2.0) v0.1.1 @ 288d34c, our nuPlan fine-tune of its
# public checkpoint (staged as container/assets/py123d/q: model.pth, the run's config.yaml, and the PUBLIC
# resnet34_v0.1.0/sensor_rig_0.yaml: our node-local training runs export a rig without cameras), plus our add-ons
# (src/garage_addons/entry.py): the GTRS-Dense judge (margin 3, radius 3 m) and the organisers' trajectory time warp
# at 1.10 on near-straight plans, skipped when the judge substituted its path (LEDGER 2026-10-09/10).
# Mirrors py123d's lib/alpasim/tools/submission.Dockerfile.
# Build (from alpasim-jepa/; inputs staged under container/assets and ext/py123d_garage):
#   docker buildx build --platform linux/amd64 --load -f container/Dockerfile.p \
#     --build-context run=container/assets/py123d/q --build-context gtrs=container/assets/gtrs --build-context wheels=container/assets/wheels \
#     --build-context addons=src --build-context legal=container -t local/q:<n> ext/py123d_garage
FROM nvidia/cuda:12.8.1-cudnn-runtime-ubuntu24.04

ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 TORCH_HOME=/tmp/torch

RUN apt-get update \
    && apt-get install -y --no-install-recommends python3.12 python3.12-venv python3-pip git libgl1 libglib2.0-0 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN python3.12 -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}" UV_LINK_MODE=copy
RUN /opt/venv/bin/pip install --no-cache-dir uv==0.8.24   # py123d copies uv 0.8 from ghcr.io; PyPI avoids that registry

COPY pyproject.toml /opt/py123d-garage/pyproject.toml
RUN uv pip install --python /opt/venv/bin/python -r /opt/py123d-garage/pyproject.toml --extra alpasim

COPY . /opt/py123d-garage
RUN uv pip install --python /opt/venv/bin/python --no-deps /opt/py123d-garage

COPY --from=wheels . /tmp/wheels
RUN uv pip install --python /opt/venv/bin/python --no-deps /tmp/wheels/alpasim_grpc-0.54.0-py3-none-any.whl && rm -rf /tmp/wheels \
    && python -c "import alpasim_grpc, torch, py123d_garage; assert alpasim_grpc.__version__ == (0, 54, 0); print('deps ok', torch.__version__)"

COPY --from=run model.pth /opt/checkpoint/model.pth
COPY --from=run config.yaml /opt/checkpoint/config.yaml
COPY --from=run sensor_rig_0.yaml /opt/checkpoint/sensor_rig.yaml

# our add-ons (judge + time warp; the judge reuses the WA-JEPA thread's GTRS wrapper) and the licence notice the
# challenge terms require (section 5)
COPY --from=addons garage_addons /opt/addons/garage_addons
COPY --from=addons wajepa_challenge/__init__.py wajepa_challenge/judge.py wajepa_challenge/navigation.py \
     wajepa_challenge/route_bridge.py wajepa_challenge/timewarp.py /opt/addons/wajepa_challenge/
COPY --from=addons wajepa_challenge/gtrs /opt/addons/wajepa_challenge/gtrs
COPY --from=gtrs gtrs_dense_resnet_sim_reward_navhard.ckpt navsim_16384.npy /opt/assets/gtrs/
COPY --from=legal LICENSE /opt/LICENSE
COPY --from=legal NOTICE.q /opt/NOTICE
RUN cd /opt/addons && python -c "import garage_addons, wajepa_challenge.judge, wajepa_challenge.route_bridge; print('addons ok')" \
    && sha256sum /opt/assets/gtrs/* /opt/checkpoint/*

ARG GIT_HASH=unknown
ENV PYTHONPATH=/opt/addons GARAGE_TIME_SCALE=1.10 GARAGE_TS_MAX_TURN_DEG=10 GARAGE_TS_SKIP_JUDGED=1 \
    GARAGE_JUDGE=gtrs GARAGE_JUDGE_MARGIN=3 GARAGE_JUDGE_RADIUS=3 GARAGE_JUDGE_COMMAND=organisers \
    GARAGE_GTRS_CHECKPOINT=/opt/assets/gtrs/gtrs_dense_resnet_sim_reward_navhard.ckpt \
    GARAGE_GTRS_VOCAB=/opt/assets/gtrs/navsim_16384.npy \
    PY123D_GARAGE_CONFIG="hydra.run.dir=/tmp/alpasim_driver \
policy_config.evaluation_checkpoint_file=/opt/checkpoint/model.pth \
policy_config.evaluation_sensor_rig_file=/opt/checkpoint/sensor_rig.yaml \
git_hash=${GIT_HASH}"
ENV HOME=/tmp MPLCONFIGDIR=/tmp/matplotlib OMP_NUM_THREADS=8
ENTRYPOINT ["sh", "-c", "exec python -m garage_addons.entry ${PY123D_GARAGE_CONFIG} host=\"${ALPASIM_DRIVER_HOST:-0.0.0.0}\" port=\"${ALPASIM_DRIVER_PORT:-6789}\" \"$@\"", "sh"]
