"""Checks before training the route pilot (one GPU, a few samples):
  1. predict_from_cache(cached context) == model.predict_trajectory(raw images), same inputs, no target point;
  2. after install(), with a target point and the zero-initialised encoder, the prediction is unchanged;
  3. the trainable parameter list (names and count);
  4. one flow_loss backward: gradients reach only trainable parameters.
"""
import sys

import numpy as np
import torch

from wajepa_route.cache_features import encode, load_model
from wajepa_route.route_model import flow_loss, freeze_all_but_trajectory, install, predict_from_cache, trainable_names
from wajepa_route.samples import build_sample, list_scenes

root, repo, config, ckpt, logs = sys.argv[1:6]
dev = torch.device("cuda")
model, _ = load_model(repo, config, ckpt, dev)
scenes = list_scenes(root, "nuplan_train", 4.0, log_names=logs.split(","))[:6]
samples = [s for s in (build_sample(sc) for sc in scenes) if s is not None]
imgs = torch.from_numpy(np.stack([s.images for s in samples])).to(dev)
ego = torch.from_numpy(np.stack([s.ego_status for s in samples])).to(dev)
hist = torch.from_numpy(np.stack([s.history_trajectory for s in samples])).to(dev)
fut = torch.from_numpy(np.stack([s.future_trajectory for s in samples])).to(dev)
tp = torch.from_numpy(np.stack([s.target_point for s in samples])).to(dev)
ac = torch.autocast("cuda", dtype=torch.bfloat16)
with ac:
    ctx, tgt = encode(model, imgs)
    x = imgs[:, :4].permute(0, 1, 2, 5, 3, 4).float().div(255).mul(2).sub(1).clamp(-1, 1)
    ref = model.predict_trajectory({"history_images": x, "ego_status": ego, "history_trajectory": hist})
    mine = predict_from_cache(model, ctx, ego, hist)
d = (ref.float() - mine.float()).abs().max().item()
print(f"1. predict_trajectory vs cached path: max |diff| {d:.4f} m  (ref end {ref[0, -1].tolist()})")
install(model)
with ac:
    mine_tp = predict_from_cache(model, ctx, ego, hist, target_point=tp)
print(f"2. zero-init target-point encoder: max |diff| {(mine_tp.float() - mine.float()).abs().max().item():.6f}")
names = trainable_names(model)
params = freeze_all_but_trajectory(model)
print(f"3. trainable: {len(names)} tensors, {sum(p.numel() for p in params) / 1e6:.1f}M of "
      f"{sum(p.numel() for p in model.parameters()) / 1e6:.1f}M parameters")
print("   e.g.", sorted({n.split('.')[1] if not n.startswith('predictor.blocks') else '.'.join(n.split('.')[3:5]) for n in names}))
model.train()
with ac:
    loss = flow_loss(model, ctx, tgt, ego, hist, fut, target_point=tp)
loss.backward()
bad = [n for n, p in model.named_parameters() if p.grad is not None and n not in set(names)]
got = sum(1 for n, p in model.named_parameters() if p.grad is not None)
print(f"4. loss {loss.item():.4f}; params with grad {got}; outside the trainable set: {bad[:5]}")
print(f"   ADE/FDE of the released model on these {len(samples)} samples: "
      f"{(ref[..., :2].float() - fut[..., :2]).norm(dim=-1).mean().item():.2f} / "
      f"{(ref[:, -1, :2].float() - fut[:, -1, :2]).norm(dim=-1).mean().item():.2f} m")
