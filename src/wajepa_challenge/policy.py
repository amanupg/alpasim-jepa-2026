"""WA-JEPA policy behind the organisers' predict_batch boundary.

Loads the released checkpoint with WA-JEPA's own `build_world_model` + strict
`load_checkpoint`, keeps fp32 weights and runs under bf16 autocast (the authors note that
casting weights to bf16 does NOT reproduce their numbers). Output: [8, 3] (x, y, yaw) at
0.5 s, ego frame x forward / y left, which is what `trajectory.make_cached_plan` expects.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass

import numpy as np
import torch

from .preprocessing import CAMERA_IDS, INPUT_H, INPUT_W, NUM_HISTORY, frames_to_tensor

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class InferenceInput:
    history: list                    # NUM_HISTORY dicts camera_id -> uint8 256x512x3, oldest first
    history_trajectory: np.ndarray   # [NUM_HISTORY, 3] relative (x, y, yaw), last row = 0
    ego_status: np.ndarray           # [8]

    def __post_init__(self) -> None:
        if len(self.history) != NUM_HISTORY:
            raise ValueError(f"need {NUM_HISTORY} history frames, got {len(self.history)}")
        for f in self.history:
            missing = [c for c in CAMERA_IDS if c not in f]
            if missing:
                raise ValueError(f"missing cameras {missing}")


@dataclass(frozen=True)
class Prediction:
    trajectory: np.ndarray


class WaJepaPolicy:
    def __init__(self, repo_root: str, config_path: str, checkpoint_path: str,
                 device: str = "cuda", warm_up: bool = True) -> None:
        from omegaconf import OmegaConf

        t0 = time.time()
        self.device = torch.device(device)
        if self.device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available")
        self.autocast = self.device.type == "cuda"
        repo_root = os.path.abspath(repo_root)
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        cfg = OmegaConf.load(config_path)
        OmegaConf.set_struct(cfg, False)
        # inference restores the trained state dict: no V-JEPA pretrained init needed
        cfg.model.require_pretrained = False
        cfg.model.vjepa2_ckpt = None
        cfg.model.init_from_checkpoint = None
        cfg.model.require_init_from_checkpoint = False
        cfg_dict = OmegaConf.to_container(cfg, resolve=True)
        m = cfg_dict["model"]
        want = ([c.lower() for c in m["camera_names"]], tuple(m["input_hw"]), int(m["num_history_frames"]),
                int(m["trajectory_horizon"]), int(m["ego_status_dim"]))
        have = (["cam_l0", "cam_f0", "cam_r0", "cam_b0"], (INPUT_H, INPUT_W), NUM_HISTORY, 8, 8)
        if want != have:
            raise RuntimeError(f"checkpoint contract {want} != adapter contract {have}")

        from models.factory import build_world_model
        from training.checkpoint import load_checkpoint

        model = build_world_model(cfg_dict).to(self.device)
        load_checkpoint(checkpoint_path, model, map_location=str(self.device), log_fn=LOGGER.info)   # strict
        self.model = model.eval()
        LOGGER.info("WA-JEPA loaded in %.0fs (cuda allocated %.2f GB)", time.time() - t0,
                    torch.cuda.memory_allocated() / 1e9 if self.autocast else 0.0)
        if warm_up:
            z = np.zeros((INPUT_H, INPUT_W, 3), np.uint8)
            req = InferenceInput(history=[{c: z for c in CAMERA_IDS}] * NUM_HISTORY,
                                 history_trajectory=np.zeros((NUM_HISTORY, 3), np.float32),
                                 ego_status=np.array([0, 1, 0, 0, 0, 0, 0, 0], np.float32))
            for _ in range(2):
                self.predict_batch([req])
            LOGGER.info("WA-JEPA warm-up done; peak reserved %.2f GiB",
                        torch.cuda.max_memory_reserved() / 2**30 if self.autocast else 0.0)

    @torch.inference_mode()
    def predict_batch(self, requests: list[InferenceInput]) -> list[Prediction]:
        if not requests:
            return []
        feats = {
            "history_images": torch.stack([frames_to_tensor(r.history) for r in requests]).to(self.device),
            "ego_status": torch.from_numpy(np.stack([r.ego_status for r in requests])).to(self.device),
            "history_trajectory": torch.from_numpy(np.stack([r.history_trajectory for r in requests])).to(self.device),
        }
        ctx = torch.autocast("cuda", dtype=torch.bfloat16) if self.autocast else torch.autocast("cpu", enabled=False)
        with ctx:
            pred = self.model.predict_trajectory(feats)
        traj = pred.float().cpu().numpy().astype(np.float64)
        if traj.shape != (len(requests), 8, 3):
            raise ValueError(f"WA-JEPA trajectory must be ({len(requests)}, 8, 3); got {traj.shape}")
        if not np.isfinite(traj).all():
            raise ValueError("WA-JEPA trajectory contains non-finite values")
        return [Prediction(trajectory=t.copy()) for t in traj]
