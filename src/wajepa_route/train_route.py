"""Train the route-conditioned trajectory stream of WA-JEPA on cached features (see route_model.py).

Data: shards from cache_features.py (<cache>/<split>/*.pt). Training reads shards in random order and shuffles inside
a buffer of shards. Every --eval-every steps, and at the end, the val shards are scored with the full 4-step
inference (`predict_from_cache`) against the released model on the same samples: ADE / FDE overall, on turns
(|lateral offset at 4 s| > 3 m in the ground truth) and the lateral error at 4 s.
Checkpoint: only the trainable tensors + the target-point encoder (`<out>/step<N>.pt`), loaded over the released
weights by the driver.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import time

import torch
from torch.utils.data import DataLoader, IterableDataset, get_worker_info

from wajepa_route.cache_features import load_model
from wajepa_route.route_model import flow_loss, freeze_all_but_trajectory, install, predict_from_cache, trainable_names

KEYS = ("context_scene", "target_scene", "ego_status", "history_trajectory", "future_trajectory", "target_point")


class ShardStream(IterableDataset):
    def __init__(self, paths, shuffle: bool, buffer_shards: int = 3, seed: int = 0, epochs: int = 1):
        self.paths, self.shuffle, self.buffer_shards, self.seed, self.epochs = list(paths), shuffle, buffer_shards, seed, epochs

    def __iter__(self):
        info = get_worker_info()
        wid, nw = (info.id, info.num_workers) if info else (0, 1)
        for ep in range(self.epochs):
            rng = random.Random(self.seed + 1000 * ep + wid)
            paths = self.paths[:]
            if self.shuffle:
                random.Random(self.seed + ep).shuffle(paths)
            paths = paths[wid::nw]
            buf = []
            for i, p in enumerate(paths):
                d = torch.load(p, map_location="cpu", weights_only=False)
                buf += [{k: d[k][j] for k in KEYS} for j in range(d["context_scene"].size(0))]
                if len(buf) >= 64 * self.buffer_shards or i == len(paths) - 1:
                    if self.shuffle:
                        rng.shuffle(buf)
                    yield from buf
                    buf = []


def batches(loader, device):
    for b in loader:
        yield {k: v.to(device, non_blocking=True) for k, v in b.items()}


@torch.no_grad()
def evaluate(model, val_paths, device, with_tp: bool, max_samples: int):
    model.eval()
    loader = DataLoader(ShardStream(val_paths, shuffle=False), batch_size=16, num_workers=2)
    err, err_end, lat_end, turn = [], [], [], []
    n = 0
    for b in batches(loader, device):
        with torch.autocast("cuda", dtype=torch.bfloat16):
            pred = predict_from_cache(model, b["context_scene"], b["ego_status"], b["history_trajectory"],
                                      b["target_point"] if with_tp else None).float()
        gt = b["future_trajectory"].float()
        e = (pred[..., :2] - gt[..., :2]).norm(dim=-1)
        err.append(e.mean(1)); err_end.append(e[:, -1])
        lat_end.append((pred[:, -1, 1] - gt[:, -1, 1]).abs()); turn.append(gt[:, -1, 1].abs() > 3.0)
        n += gt.size(0)
        if max_samples and n >= max_samples:
            break
    err, err_end, lat_end, turn = map(torch.cat, (err, err_end, lat_end, turn))
    out = {"n": int(err.numel()), "ade": err.mean().item(), "fde": err_end.mean().item(), "lat4s": lat_end.mean().item(),
           "n_turn": int(turn.sum()), "ade_turn": err[turn].mean().item() if turn.any() else float("nan"),
           "fde_turn": err_end[turn].mean().item() if turn.any() else float("nan"),
           "lat4s_turn": lat_end[turn].mean().item() if turn.any() else float("nan")}
    model.train()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--train-split", default="nuplan_train")
    ap.add_argument("--val-split", default="nuplan_val")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--warmup", type=int, default=200)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--eval-every", type=int, default=2000)
    ap.add_argument("--eval-max", type=int, default=2000)
    ap.add_argument("--no-target-point", action="store_true", help="control: same fine-tune without the route input")
    ap.add_argument("--target-point-only", action="store_true",
                    help="train only the target-point encoder (no drift of the released weights)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    torch.manual_seed(0)
    dev = torch.device("cuda")
    model, _ = load_model(a.repo, a.config, a.checkpoint, dev)
    install(model)
    params = freeze_all_but_trajectory(model, only_target_point=a.target_point_only)
    names = trainable_names(model, only_target_point=a.target_point_only)
    with_tp = not a.no_target_point
    train_paths = sorted(glob.glob(f"{a.cache}/{a.train_split}/*.pt"))
    val_paths = sorted(glob.glob(f"{a.cache}/{a.val_split}/*.pt"))
    n_train = 64 * len(train_paths)                     # shards hold up to 64 samples
    steps_total = a.epochs * n_train // a.batch
    log = open(os.path.join(a.out, "log.jsonl"), "a")

    def emit(rec):
        print(json.dumps(rec), flush=True)
        log.write(json.dumps(rec) + "\n"); log.flush()

    emit({"event": "start", "train_shards": len(train_paths), "val_shards": len(val_paths), "steps": steps_total,
          "trainable_tensors": len(names), "trainable_params_m": sum(p.numel() for p in params) / 1e6,
          "with_target_point": with_tp, "args": vars(a)})
    # The released model (zero-init encoder = no route effect), on the periodic subset and on the full val set.
    emit({"event": "eval", "step": 0, "model": "released", "subset": True,
          **evaluate(model, val_paths, dev, with_tp=False, max_samples=a.eval_max)})
    base_full = evaluate(model, val_paths, dev, with_tp=False, max_samples=0)
    emit({"event": "eval", "step": 0, "model": "released", "subset": False, **base_full})
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.04, betas=(0.9, 0.999))
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / a.warmup) *
                                              0.5 * (1 + math.cos(math.pi * min(s, steps_total) / max(steps_total, 1))))
    loader = DataLoader(ShardStream(train_paths, shuffle=True, epochs=a.epochs), batch_size=a.batch,
                        num_workers=a.workers, drop_last=True, persistent_workers=False, prefetch_factor=2)
    model.train()
    step, t0, run = 0, time.time(), 0.0

    def save(tag):
        state = {n: p.detach().cpu() for n, p in model.named_parameters() if n in set(names)}
        torch.save({"state_dict": state, "with_target_point": with_tp, "step": step}, os.path.join(a.out, f"{tag}.pt"))

    for b in batches(loader, dev):
        with torch.autocast("cuda", dtype=torch.bfloat16):
            loss = flow_loss(model, b["context_scene"], b["target_scene"], b["ego_status"], b["history_trajectory"],
                             b["future_trajectory"], b["target_point"] if with_tp else None)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step(); sched.step(); step += 1
        run = 0.98 * run + 0.02 * loss.item() if step > 1 else loss.item()
        if step % 50 == 0:
            emit({"event": "train", "step": step, "loss": run, "lr": sched.get_last_lr()[0],
                  "samples_per_s": step * a.batch / (time.time() - t0)})
        if step % a.eval_every == 0:
            emit({"event": "eval", "step": step, "model": "tuned", "subset": True,
                  **evaluate(model, val_paths, dev, with_tp, a.eval_max)})
            save(f"step{step:06d}")
    emit({"event": "eval", "step": step, "model": "tuned", "subset": False, **evaluate(model, val_paths, dev, with_tp, 0)})
    emit({"event": "eval", "step": step, "model": "released", "subset": False, **base_full})
    save("final")


if __name__ == "__main__":
    main()
