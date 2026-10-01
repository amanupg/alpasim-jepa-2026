# SPDX-License-Identifier: Apache-2.0
# Copied from NVlabs/alpasim e2e_challenge @ 2023534,
# e2e_challenge/sample_submission_simscale_navsim_gtrs_dense/navsim_gtrs_dense_challenge/{policy.py (checkpoint and
# vocabulary loading, everything before the GTRSDensePolicy class), preprocessing.py (all)}, unchanged apart from
# being merged into one module. Copyright (c) 2026 NVIDIA Corporation, Apache-2.0 (see LICENSE in this folder).
from __future__ import annotations


from collections.abc import Mapping, Sequence

import cv2
import numpy as np
import torch

CAMERA_IDS = ("CAM_L0", "CAM_F0", "CAM_R0")
EXPECTED_HEIGHT = 1080
EXPECTED_WIDTH = 1920
OUTPUT_HEIGHT = 512
OUTPUT_WIDTH = 2048


def _validated_image(camera_id: str, image: np.ndarray) -> np.ndarray:
    array = np.asarray(image)
    expected_shape = (EXPECTED_HEIGHT, EXPECTED_WIDTH, 3)
    if array.shape != expected_shape:
        raise ValueError(
            f"{camera_id} image must be 1920x1080 with shape {expected_shape}; "
            f"got shape {array.shape}"
        )
    if array.dtype != np.uint8:
        raise ValueError(
            f"{camera_id} image must have dtype uint8; got dtype {array.dtype}"
        )
    return array


def preprocess_images(
    images: Mapping[str, np.ndarray],
    dtype: torch.dtype = torch.float32,
) -> torch.Tensor:
    if not dtype.is_floating_point:
        raise ValueError(
            f"preprocess_images requires a floating-point dtype; got {dtype}"
        )

    missing = [camera_id for camera_id in CAMERA_IDS if camera_id not in images]
    if missing:
        raise ValueError(f"missing required cameras: {', '.join(missing)}")

    left = _validated_image("CAM_L0", images["CAM_L0"])[28:-28, 416:-416]
    front = _validated_image("CAM_F0", images["CAM_F0"])[28:-28]
    right = _validated_image("CAM_R0", images["CAM_R0"])[28:-28, 416:-416]

    panorama = np.concatenate((left, front, right), axis=1)
    resized = cv2.resize(
        panorama,
        (OUTPUT_WIDTH, OUTPUT_HEIGHT),
        interpolation=cv2.INTER_LINEAR,
    )
    tensor = torch.from_numpy(resized).permute(2, 0, 1).contiguous().to(dtype=dtype)
    return tensor.div_(255.0)


def _vector(name: str, values: Sequence[float] | np.ndarray, size: int) -> np.ndarray:
    vector = np.asarray(values, dtype=np.float32)
    if vector.shape != (size,):
        raise ValueError(f"{name} must have shape ({size},); got shape {vector.shape}")
    return vector


def build_status_feature(
    *,
    command_one_hot: Sequence[float] | np.ndarray,
    velocity_xy: Sequence[float] | np.ndarray,
    acceleration_xy: Sequence[float] | np.ndarray,
) -> torch.Tensor:
    status = np.concatenate(
        (
            _vector("command_one_hot", command_one_hot, 4),
            _vector("velocity_xy", velocity_xy, 2),
            _vector("acceleration_xy", acceleration_xy, 2),
        )
    )
    return torch.from_numpy(status)


# ---- from policy.py


import hashlib
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from os import PathLike
from pathlib import Path

import numpy as np
import torch
from torch import Tensor


LOGGER = logging.getLogger(__name__)

CHECKPOINT_PREFIX = "agent.model."
VOCABULARY_KEY = f"{CHECKPOINT_PREFIX}_trajectory_head.vocab"
NAVHARD_VOCABULARY_SHAPE = (8192, 40, 3)
CHECKPOINT_VOCABULARY_SHAPE = (16384, 40, 3)
OFFICIAL_VOCABULARIES = {
    3_932_288: (
        "cc44a31e75a53406db59f026f0358de97931e726f10254542f98d2a87a38ad35",
        NAVHARD_VOCABULARY_SHAPE,
    ),
    7_864_448: (
        "e8c29cfc25add59ae8b64769a4554c6518878726178c0bd889fc8518ebe1261d",
        CHECKPOINT_VOCABULARY_SHAPE,
    ),
}


def _validate_vocabulary(
    vocabulary: Tensor,
    *,
    expected_shape: tuple[int, int, int],
    source: str,
) -> None:
    if tuple(vocabulary.shape) != expected_shape:
        raise ValueError(
            f"{source} vocabulary must have shape {expected_shape}; "
            f"got {tuple(vocabulary.shape)}"
        )
    if vocabulary.dtype != torch.float32:
        raise ValueError(f"{source} vocabulary must use dtype float32")
    if not torch.isfinite(vocabulary).all():
        raise ValueError(f"{source} vocabulary contains non-finite values")


def load_navhard_vocabulary(path: str | PathLike[str]) -> Tensor:
    vocabulary_path = Path(path)
    try:
        size = vocabulary_path.stat().st_size
    except OSError as exc:
        raise ValueError(
            f"NAVHARD vocabulary is unavailable: {vocabulary_path}"
        ) from exc
    vocabulary_spec = OFFICIAL_VOCABULARIES.get(size)
    if vocabulary_spec is None:
        raise ValueError(
            "official vocabulary size "
            f"{size}, expected one of {sorted(OFFICIAL_VOCABULARIES)}"
        )
    expected_sha, expected_shape = vocabulary_spec

    digest = hashlib.sha256()
    with vocabulary_path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    actual_sha = digest.hexdigest()
    if actual_sha != expected_sha:
        raise ValueError(
            "official vocabulary SHA256 " f"{actual_sha}, expected {expected_sha}"
        )

    try:
        array = np.load(vocabulary_path, allow_pickle=False)
    except (OSError, ValueError) as exc:
        raise ValueError("NAVHARD vocabulary is not a valid NPY array") from exc
    vocabulary = torch.from_numpy(np.asarray(array).copy())
    _validate_vocabulary(
        vocabulary,
        expected_shape=expected_shape,
        source="official",
    )
    return vocabulary


def normalized_checkpoint(
    payload: object,
    inference_vocabulary: Tensor,
) -> dict[str, Tensor]:
    if not isinstance(payload, dict) or set(payload) != {"state_dict"}:
        raise ValueError(
            "checkpoint payload must be a dict containing only 'state_dict'"
        )
    state_dict = payload["state_dict"]
    if not isinstance(state_dict, dict):
        raise ValueError("checkpoint state_dict must be a dict")

    normalized: dict[str, Tensor] = {}
    for key, value in state_dict.items():
        if not isinstance(key, str) or not key.startswith(CHECKPOINT_PREFIX):
            raise ValueError(f"unexpected checkpoint key: {key}")
        if not isinstance(value, Tensor):
            raise ValueError(f"checkpoint value for {key} must be a tensor")
        normalized[key.removeprefix(CHECKPOINT_PREFIX)] = value

    checkpoint_vocabulary = state_dict.get(VOCABULARY_KEY)
    if not isinstance(checkpoint_vocabulary, Tensor):
        raise ValueError("checkpoint vocabulary tensor is missing")
    _validate_vocabulary(
        checkpoint_vocabulary,
        expected_shape=CHECKPOINT_VOCABULARY_SHAPE,
        source="checkpoint",
    )
    inference_shape = tuple(inference_vocabulary.shape)
    supported_shapes = {spec[1] for spec in OFFICIAL_VOCABULARIES.values()}
    if inference_shape not in supported_shapes:
        raise ValueError(
            "inference vocabulary must have a supported shape; "
            f"got {inference_shape}"
        )
    _validate_vocabulary(
        inference_vocabulary,
        expected_shape=inference_shape,
        source="inference",
    )
    normalized["_trajectory_head.vocab"] = inference_vocabulary
    return normalized


