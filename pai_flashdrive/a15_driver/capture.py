"""Training-sample capture for fine-tuning Alpamayo's action expert on simulator-rendered frames.

Local data generation only (A15_CAPTURE_DIR set). Two modes:
- force-GT (A15_NO_MODEL=1): the runtime forces the ego onto the recorded trajectory for the
whole scene (force_gt_duration_us) and sends the recording (send_recording_ground_truth), so the driver sees rendered
frames from the recorded viewpoint and knows the recorded future.
- policy-driven (DAgger, model on): the policy drives, and the runtime still sends the recording every step (in the
  ego's rig frame). Each sample is labelled with the recorded future from the ego's actual pose, i.e. a path back to
  (and along) the recording; samples farther than A15_CAPTURE_MAX_DEV_M from the recording are skipped so the labels
  stay drivable recoveries.
Every `every_us` the driver saves one sample in
exactly the form the policy consumes at inference:
  frames  : n_cam x 4 frames (0.1 s apart) at the driver's resize (576x320), JPEG-encoded
  slots   : Alpamayo camera slots of those cameras
  hist    : 16 ego poses at 0.1 s in the t0 rig frame (xyz, rotation), as the driver builds them
  future  : the recorded 64 poses at 0.1 s after t0, in the same frame (the training target)
The recording is never used at inference; the official evaluator does not send it.
"""
from __future__ import annotations

import io
import os
import threading

import numpy as np
from PIL import Image


def jpeg_bytes(chw_uint8, quality: int = 95) -> bytes:
    arr = chw_uint8.permute(1, 2, 0).contiguous().numpy()
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


class GroundTruthStore:
    """Recorded trajectory of one session in the world frame: times (N,), positions (N, 3), rotations (N, 3, 3)."""

    def __init__(self):
        self.t = None
        self.p = None
        self.R = None

    def set_from_rig(self, times_us: np.ndarray, xyz_rig: np.ndarray, R_rig: np.ndarray,
                     pos_w: np.ndarray, R_w: np.ndarray) -> None:
        """xyz_rig / R_rig: recording poses in the rig frame of the ego pose (pos_w, R_w: rig-to-world)."""
        self.t = np.asarray(times_us, dtype=np.float64)
        self.p = xyz_rig @ R_w.T + pos_w
        self.R = np.einsum("ij,njk->nik", R_w, R_rig)

    def offset_at(self, t0_us: int, pos0: np.ndarray, R0: np.ndarray):
        """Recorded position at t0 in the rig frame (pos0, R0): how far the ego is from the recording (None if not covered)."""
        if self.t is None or not (self.t[0] <= t0_us <= self.t[-1]):
            return None
        p = np.array([np.interp(t0_us, self.t, self.p[:, k]) for k in range(3)])
        return (p - pos0) @ R0

    def future_in_frame(self, t0_us: int, pos0: np.ndarray, R0: np.ndarray, n: int = 64, dt_us: int = 100_000):
        """Recorded poses at t0 + k*dt (k = 1..n) in the rig frame (pos0, R0); None if the recording does not cover them."""
        if self.t is None:
            return None
        ts = t0_us + dt_us * np.arange(1, n + 1)
        if ts[-1] > self.t[-1] or ts[0] < self.t[0]:
            return None
        p = np.stack([np.interp(ts, self.t, self.p[:, k]) for k in range(3)], 1)
        idx = np.clip(np.searchsorted(self.t, ts), 1, len(self.t) - 1)
        R = self.R[idx]                                            # nearest-after rotation (recording is 10 Hz+)
        xyz = (p - pos0) @ R0                                      # R0^T (p - p0)
        rot = np.einsum("ji,njk->nik", R0, R)                      # R0^T R
        return xyz.astype(np.float32), rot.astype(np.float32)


class Capturer:
    def __init__(self, out_dir: str, every_us: int = 500_000):
        self.out_dir, self.every_us = out_dir, int(every_us)
        os.makedirs(out_dir, exist_ok=True)
        self._lock = threading.Lock()
        self.n = 0

    def save(self, sid: str, t0_us: int, frames, slots, hx, hr, fut_xyz, fut_rot, **extra) -> None:
        jpgs = [jpeg_bytes(frames[c, f]) for c in range(frames.shape[0]) for f in range(frames.shape[1])]
        lens = np.array([len(b) for b in jpgs], dtype=np.int64)
        d = os.path.join(self.out_dir, sid)
        os.makedirs(d, exist_ok=True)
        np.savez(os.path.join(d, f"{t0_us}.npz"),
                 jpeg=np.frombuffer(b"".join(jpgs), dtype=np.uint8), jpeg_len=lens,
                 frames_shape=np.array(frames.shape, dtype=np.int64), slots=np.array(slots, dtype=np.int64),
                 hist_xyz=hx.reshape(-1, 3).numpy().astype(np.float32),
                 hist_rot=hr.reshape(-1, 3, 3).numpy().astype(np.float32),
                 fut_xyz=fut_xyz, fut_rot=fut_rot, t0_us=np.int64(t0_us), **extra)
        with self._lock:
            self.n += 1


def load_sample(path: str):
    """Inverse of Capturer.save: frames (n_cam, 4, 3, H, W) uint8 tensor and the arrays."""
    import torch
    z = np.load(path)
    shape = tuple(int(x) for x in z["frames_shape"])
    buf, lens = z["jpeg"].tobytes(), z["jpeg_len"]
    offs = np.concatenate([[0], np.cumsum(lens)])
    imgs = [np.asarray(Image.open(io.BytesIO(buf[offs[i]:offs[i + 1]])).convert("RGB")) for i in range(len(lens))]
    fr = torch.from_numpy(np.stack(imgs)).permute(0, 3, 1, 2).reshape(shape)
    return {"frames": fr, "slots": z["slots"].tolist(), "hist_xyz": z["hist_xyz"], "hist_rot": z["hist_rot"],
            "fut_xyz": z["fut_xyz"], "fut_rot": z["fut_rot"], "t0_us": int(z["t0_us"]),
            **{k: z[k] for k in ("samp_xyz", "samp_rot") if k in z.files}}
