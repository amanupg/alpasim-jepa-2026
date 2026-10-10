"""Cache WA-JEPA's frozen features for the route-conditioning pilot (one array task per slice of logs).

Per sample, through WA-JEPA's own code paths (models/multiview_causal_future_jepa.py @ bec2966):
  context_scene [4096, 512] bf16: `_encode_scene_context` on the history tokens under the full-future mask, exactly
      what `predict_trajectory` computes at inference (the encoder only sees history tubelets);
  target_scene [8192, 512] bf16: the EMA teacher's projected future tokens (`_teacher_targets` +
      `_target_future_scene`), the clean scene the flow predictor is trained towards;
  plus history_trajectory, future_trajectory, ego_status, target_point and ids.
Both encoders stay frozen in the pilot, so these are exact inputs for training the trajectory stream.
Output: <out>/<split>/task<i>_<k>.pt shards of up to SHARD samples.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset

from wajepa_route.samples import build_sample, list_scenes
from py123d_garage.py123d_help.scene_builders.scene_builder import find_log_names


class SampleDataset(Dataset):
    def __init__(self, scenes):
        self.scenes = scenes

    def __len__(self):
        return len(self.scenes)

    def __getitem__(self, i):
        try:
            s = build_sample(self.scenes[i])
        except Exception as e:                                     # a broken log must not stop the task
            print(f"sample error {self.scenes[i].log_name}: {type(e).__name__}: {e}", file=sys.stderr)
            return None
        if s is None:
            return None
        return {"images": torch.from_numpy(s.images), "history_trajectory": torch.from_numpy(s.history_trajectory),
                "future_trajectory": torch.from_numpy(s.future_trajectory), "ego_status": torch.from_numpy(s.ego_status),
                "target_point": torch.from_numpy(s.target_point), "log_name": s.log_name, "timestamp_us": s.timestamp_us}


def collate(items):
    items = [x for x in items if x is not None]
    if not items:
        return None
    out = {k: torch.stack([x[k] for x in items]) for k in items[0] if isinstance(items[0][k], torch.Tensor)}
    out["log_name"] = [x["log_name"] for x in items]
    out["timestamp_us"] = torch.tensor([x["timestamp_us"] for x in items], dtype=torch.int64)
    return out


def load_model(repo: str, config: str, checkpoint: str, device: torch.device):
    from omegaconf import OmegaConf
    sys.path.insert(0, repo)
    cfg = OmegaConf.load(config)
    OmegaConf.set_struct(cfg, False)
    cfg.model.require_pretrained = False
    cfg.model.vjepa2_ckpt = None
    cfg.model.init_from_checkpoint = None
    cfg.model.require_init_from_checkpoint = False
    cfg_dict = OmegaConf.to_container(cfg, resolve=True)
    from models.factory import build_world_model
    from training.checkpoint import load_checkpoint
    model = build_world_model(cfg_dict).to(device)
    load_checkpoint(checkpoint, model, map_location=str(device))          # strict: the released weights unchanged
    return model.eval(), cfg_dict


@torch.no_grad()
def encode(model, images: torch.Tensor):
    """images [B, 12, 4, H, W, 3] uint8 -> context_scene [B, 4096, 512], target_scene [B, 8192, 512] (bf16)."""
    x = images.permute(0, 1, 2, 5, 3, 4).float().div_(255.0).mul_(2.0).sub_(1.0).clamp_(-1.0, 1.0)  # as frames_to_tensor
    nh = model.num_history_frames
    history, future = x[:, :nh], x[:, nh:]
    bsz = x.size(0)
    clip = model._make_full_clip(history, future)
    masks = model.mask_sampler.full_future_mask(bsz, device=clip.device)
    idx, masks_x = masks.indices[0], masks.masks_x[0]
    view_idx = (idx.unsqueeze(1) * model.num_cameras + torch.arange(model.num_cameras, device=clip.device).unsqueeze(0)).reshape(-1)
    context = model._encode_scene_context(clip.index_select(0, view_idx), masks_x.index_select(0, idx), idx.numel())
    targets = model._teacher_targets(clip, bsz)
    target_scene = model._target_future_scene(targets)
    return context.to(torch.bfloat16), target_scene.to(torch.bfloat16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--anchor-spacing-s", type=float, default=4.0)
    ap.add_argument("--task", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_ID", 0)))
    ap.add_argument("--tasks", type=int, default=int(os.environ.get("SLURM_ARRAY_TASK_COUNT", 1)))
    ap.add_argument("--max-samples", type=int, default=0)
    ap.add_argument("--logs", default="", help="comma-separated log names (tests); default: this task's slice")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--shard", type=int, default=64)
    a = ap.parse_args()

    logs = a.logs.split(",") if a.logs else find_log_names(a.data_root, [a.split])[a.task::a.tasks]
    t0 = time.time()
    scenes = list_scenes(a.data_root, a.split, a.anchor_spacing_s, log_names=logs)
    if a.max_samples:
        scenes = scenes[: a.max_samples]
    print(f"task {a.task}/{a.tasks}: {len(logs)} logs, {len(scenes)} scenes ({time.time() - t0:.0f} s)", flush=True)
    device = torch.device("cuda")
    model, _ = load_model(a.repo, a.config, a.checkpoint, device)
    out_dir = os.path.join(a.out, a.split)
    os.makedirs(out_dir, exist_ok=True)
    loader = DataLoader(SampleDataset(scenes), batch_size=a.batch, num_workers=a.workers, collate_fn=collate,
                        prefetch_factor=2 if a.workers else None, persistent_workers=False,
                        timeout=300 if a.workers else 0)   # a stalled worker raises instead of hanging the job
    buf, k, n_done, t1 = [], 0, 0, time.time()

    def flush():
        nonlocal buf, k
        if not buf:
            return
        shard = {key: (torch.cat([b[key] for b in buf]) if isinstance(buf[0][key], torch.Tensor)
                       else sum((b[key] for b in buf), [])) for key in buf[0]}
        path = os.path.join(out_dir, f"task{a.task:03d}_{k:04d}.pt")
        torch.save(shard, path + ".tmp")
        os.replace(path + ".tmp", path)                          # never leave a half-written shard
        buf, k = [], k + 1

    for batch in loader:
        if batch is None:
            continue
        with torch.autocast("cuda", dtype=torch.bfloat16):
            ctx, tgt = encode(model, batch.pop("images").to(device, non_blocking=True))
        batch.update(context_scene=ctx.cpu(), target_scene=tgt.cpu())
        buf.append(batch)
        n_done += ctx.size(0)
        if sum(b["context_scene"].size(0) for b in buf) >= a.shard:
            flush()
            print(f"{n_done} samples, {n_done / (time.time() - t1):.2f} samples/s", flush=True)
    flush()
    from wajepa_route.samples import SKIP_REASONS
    print(f"task {a.task} done: {n_done} samples in {time.time() - t1:.0f} s (skips in the main process: "
          f"{SKIP_REASONS}; worker skips are logged per worker)", flush=True)


if __name__ == "__main__":
    main()
