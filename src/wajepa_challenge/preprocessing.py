"""WA-JEPA inputs for the AlpaSim nuPlan/MTGS track.

Matches WA-JEPA's NAVSIM feature builder (`eval/navsim_agent.py::WorldModelFeatureBuilder`,
upstream bec2966) exactly:
  * cameras, in this ORDER (the model has a learned per-slot camera embedding):
    cam_l0, cam_f0, cam_r0, cam_b0 -> AlpaSim logical ids CAM_L0, CAM_F0, CAM_R0, CAM_B0;
  * full frame, no crop, RGB, cv2.resize to 512x256 with INTER_AREA, scaled to [-1, 1];
  * 4 history frames, oldest first, 0.5 s apart (the track delivers 2 Hz frames, so stride 1);
  * ego_status = [command one-hot(4) (0 left, 1 straight, 2 right, 3 unknown), vx, vy, ax, ay];
  * history_trajectory = last 4 poses (x, y, yaw) relative to the current pose, x fwd, y left.
Frames are resized once on arrival (uint8, 256x512) to keep per-session memory small.
"""
from __future__ import annotations

import math

import cv2
import numpy as np
import torch

CAMERA_IDS = ("CAM_L0", "CAM_F0", "CAM_R0", "CAM_B0")
INPUT_H, INPUT_W = 256, 512
NUM_HISTORY = 4


def resize_frame(image_rgb: np.ndarray) -> np.ndarray:
    """uint8 HxWx3 RGB -> uint8 256x512x3 (INTER_AREA, as in WA-JEPA's NAVSIM builder)."""
    out = cv2.resize(np.ascontiguousarray(image_rgb), (INPUT_W, INPUT_H), interpolation=cv2.INTER_AREA)
    out.setflags(write=False)
    return out


def frames_to_tensor(history: list[dict[str, np.ndarray]]) -> torch.Tensor:
    """[T][camera] uint8 256x512x3 -> float tensor [T, V, 3, 256, 512] in [-1, 1]."""
    per_t = []
    for frame in history:
        per_t.append(np.stack([frame[c] for c in CAMERA_IDS], 0))          # [V, H, W, 3]
    arr = np.stack(per_t, 0)                                                 # [T, V, H, W, 3]
    t = torch.from_numpy(arr).permute(0, 1, 4, 2, 3).float().div_(255.0)
    return t.mul_(2.0).sub_(1.0).clamp_(-1.0, 1.0)


def relative_se2(poses_xyyaw: np.ndarray) -> np.ndarray:
    """Absolute (x, y, yaw) rows -> relative to the LAST row (WA-JEPA's
    convert_absolute_to_relative_se2_array: rotate by -yaw0, wrap yaw)."""
    p = np.asarray(poses_xyyaw, dtype=np.float64).copy()
    ox, oy, oh = p[-1]
    c, s = math.cos(-oh), math.sin(-oh)
    rot = np.array([[c, -s], [s, c]])
    p[:, 0] -= ox; p[:, 1] -= oy; p[:, 2] -= oh
    p[:, :2] = p[:, :2] @ rot.T
    p[:, 2] = np.arctan2(np.sin(p[:, 2]), np.cos(p[:, 2]))
    return p.astype(np.float32)


def build_ego_status(command_one_hot: np.ndarray, velocity_xy: np.ndarray, acceleration_xy: np.ndarray) -> np.ndarray:
    st = np.concatenate([np.asarray(command_one_hot, np.float32).reshape(4),
                         np.asarray(velocity_xy, np.float32).reshape(2),
                         np.asarray(acceleration_xy, np.float32).reshape(2)])
    if not np.isfinite(st).all():
        raise ValueError("ego status contains non-finite values")
    return st


# ---- PAI track (diagnostic, WAJEPA_RIG=pai): map the NVIDIA rig onto WA-JEPA's nuPlan slots.
# PAI sends 10 Hz frames from 120-degree f-theta cameras (front wide, cross left/right), 70-degree
# rear corners and a 30-degree tele; there is no straight-back camera. nuPlan's L0/F0/R0/B0 are
# ~64-degree pinhole cameras at about +55/0/-55/180 degrees. Crop boxes are image fractions
# (x0, y0, x1, y1), derived from equal angle per pixel over the 120-degree width (~16 px/deg):
#   front: centre 64 deg -> 0.53 of the width, vertical 38.5 deg -> 0.57 of the height;
#   cross left (assumed to face +90 deg, forward edge on the image's right): 30-94 deg -> x 0.47-1.0;
#   cross right: mirror -> x 0.0-0.53. The rear slot gets mid-grey (no matching camera).
GREY = "grey"
PAI_VIEWS: dict[str, dict[str, tuple[str, tuple[float, float, float, float]]]] = {
    "resize": {
        "CAM_L0": ("camera_cross_left_120fov", (0.0, 0.0, 1.0, 1.0)),
        "CAM_F0": ("camera_front_wide_120fov", (0.0, 0.0, 1.0, 1.0)),
        "CAM_R0": ("camera_cross_right_120fov", (0.0, 0.0, 1.0, 1.0)),
        "CAM_B0": (GREY, (0.0, 0.0, 1.0, 1.0)),
    },
    "crop": {
        "CAM_L0": ("camera_cross_left_120fov", (0.47, 0.215, 1.0, 0.785)),
        "CAM_F0": ("camera_front_wide_120fov", (0.235, 0.215, 0.765, 0.785)),
        "CAM_R0": ("camera_cross_right_120fov", (0.0, 0.215, 0.53, 0.785)),
        "CAM_B0": (GREY, (0.0, 0.0, 1.0, 1.0)),
    },
}


def crop_frac(image_rgb: np.ndarray, box: tuple[float, float, float, float]) -> np.ndarray:
    h, w = image_rgb.shape[:2]
    x0, y0, x1, y1 = box
    return image_rgb[int(round(y0 * h)):int(round(y1 * h)), int(round(x0 * w)):int(round(x1 * w))]


def grey_frame() -> np.ndarray:
    out = np.full((INPUT_H, INPUT_W, 3), 128, np.uint8)
    out.setflags(write=False)
    return out
