"""Fine-tune py123d_garage's planning decoder on closed-loop records with recovery labels (DAgger-style).

The policy is built and loaded exactly as the AlpaSim driver does (same hydra config and overrides, e.g.
policy_config.evaluation_checkpoint_files=[...]); the backbone and every other head stay frozen in eval mode, so only
`planning_decoder` (its context encoder and flow decoder) trains, with py123d's own flow-matching loss and loss weights
(trajectory, path, action), and the training-time conditioning of `_forward_heads` (target point dropout etc.).

Env: CL_DATA (dirs of collect.py .pt files, ':'-separated), CL_OUT (output .pth), CL_EPOCHS (4), CL_LR (2e-5),
CL_BATCH (32), CL_VAL_FRAC (0.1, by scene), CL_SEED (0), CL_MAX_RECORDS (0 = all),
CL_TIMING ("log": recovery labels with the log's timing, round 1; "own": lateral-only, the policy's own speed profile;
"self": control, the policy's own served plan as the trajectory label), CL_ZERO_LOSSES (comma list of loss names whose
weight is set to 0, e.g. loss_path for the "self" control, whose path label still comes from the log).
The output keeps the released checkpoint's plain state-dict layout (keys it holds that the model does not are copied).
"""
from __future__ import annotations

import glob
import logging
import math
import os
import random
import zlib

import hydra
import numpy as np
import torch
from omegaconf import DictConfig
from torchvision.io import decode_jpeg

from closed_loop.labels import recovery_labels
from py123d_garage.api.abstract_policy_tensors import NavigationConditioning
from py123d_garage.common.config_help import CONFIG_PATH, finalize_evaluation, hydra_overrides, register_schema
from py123d_garage.common.logging_setup import setup_logging
from py123d_garage.config.schema.evaluation.alpasim_config import AlpasimBenchmarkConfig
from py123d_garage.evaluation.alpasim.help.config_help import build_policy
from py123d_garage.policy.transfuser.features import TransfuserFeatures
from py123d_garage.policy.transfuser.network.decoder.unicycle import fit_actions

LOG = logging.getLogger("closed_loop.train")
register_schema("evaluate_alpasim", AlpasimBenchmarkConfig)


def load_samples(dirs: list[str], max_records: int, timing: str = "log"):
    samples, skipped = [], 0
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "*.pt"))):
            blob = torch.load(f, map_location="cpu", weights_only=False)
            if blob["gt_local"] is None:
                skipped += len(blob["records"])
                continue
            for rec in blob["records"]:
                if rec["features"] is None or rec["navigation"] is None:
                    skipped += 1
                    continue
                lab = recovery_labels(rec, blob["gt_local"], "own" if timing == "self" else timing)
                if lab is not None and timing == "self":        # control: the policy's own served plan as the label
                    lab = (_own_plan(rec), lab[1], lab[2])
                if lab is None:
                    skipped += 1
                    continue
                samples.append({"scene": blob["scene_id"], "features": rec["features"], "navigation": rec["navigation"],
                                "trajectory": torch.from_numpy(lab[0]), "path": torch.from_numpy(lab[1]),
                                "lateral": lab[2]["lateral"], "perturbed": rec.get("perturb_m", 0.0) != 0.0})
                if max_records and len(samples) >= max_records:
                    return samples, skipped
    return samples, skipped


def _own_plan(rec) -> np.ndarray:
    """The served plan [64, 3] with collect.py's lateral perturbation ramp removed (self-distillation control)."""
    poses = np.asarray(rec["served_poses"], np.float32).copy()
    offset = rec.get("perturb_m", 0.0)
    if offset:
        poses[:, 1] -= offset * np.clip(np.arange(1, 65) * 0.1 / 1.5, 0.0, 1.0)
    return poses


def _features(sample) -> dict[str, torch.Tensor]:
    f = dict(sample["features"])
    if "camera_feature_jpeg" in f:                               # collect.py stores the camera feature as JPEG
        f["camera_feature"] = decode_jpeg(f.pop("camera_feature_jpeg"))
    return f


def batch_of(samples, device):
    decoded = [_features(s) for s in samples]
    feats = {k: torch.stack([f[k] for f in decoded]).to(device) for k in decoded[0]}
    nav = {k: torch.stack([s["navigation"][k] for s in samples]).to(device) for k in samples[0]["navigation"]}
    return (TransfuserFeatures(**feats), NavigationConditioning(**nav),
            torch.stack([s["trajectory"] for s in samples]).to(device), torch.stack([s["path"] for s in samples]).to(device))


def planning_label(policy, features, trajectory, path):
    config = policy.policy_config
    label = trajectory[:, : config.trajectory_num_steps]
    action_config = config.planning_config.unicycle_action_config
    if action_config is not None:
        speeds = features.velocity.reshape(-1)
        actions = torch.stack([fit_actions(t, v, action_config) for t, v in zip(trajectory.cpu(), speeds.cpu())])
        label = torch.cat([label, actions.to(label.device, label.dtype)], dim=-1)
    if config.planning_config.path_config is not None:
        label = torch.cat([label, torch.nn.functional.pad(path, (0, label.shape[-1] - path.shape[-1]))], dim=1)
    return label


def train_loss(policy, features, navigation, trajectory, path, weights):
    with torch.no_grad():
        lidar = None if policy.policy_config.backbone_config.latent else features.lidar_feature
        bev, image, registers = policy.backbone(features.camera_feature.float(), lidar)
    predictions = policy._forward_heads(features, navigation, bev, image, registers)
    losses = policy.planning_decoder.compute_loss(predictions.trajectory, planning_label(policy, features, trajectory, path))
    total = sum(weights[name] * value.float() for name, value in losses.items())
    return total, losses


def cross_track(driven, path):
    """Mean distance of the driven waypoints [B, T, 2] to the label path polyline [B, P, 2] (timing-free), over the
    waypoints no farther from the ego than the path's end (the path label covers 64 m)."""
    a, b = path[:, None, :-1], path[:, None, 1:]                       # [B, 1, P-1, 2]
    ab = b - a
    ap = driven[:, :, None] - a                                        # [B, T, P-1, 2]
    u = ((ap * ab).sum(-1) / (ab * ab).sum(-1).clamp_min(1e-9)).clamp(0, 1)
    d = (ap - u[..., None] * ab).norm(dim=-1).min(dim=-1).values       # [B, T]
    inside = (driven.norm(dim=-1) <= path[:, -1].norm(dim=-1, keepdim=True)).float()
    return (d * inside).sum(dim=-1) / inside.sum(dim=-1).clamp_min(1.0)


@torch.no_grad()
def sampled_l1(policy, samples, device, batch):
    """Mean L1 of the sampled waypoints (eval mode, as driven) to the trajectory labels, and mean cross-track distance
    to the path label; each on all records and on off-log ones (|e| > 0.3 m)."""
    policy.eval()
    errs, off, xt, xt_off = [], [], [], []
    for i in range(0, len(samples), batch):
        chunk = samples[i: i + batch]
        features, navigation, trajectory, path = batch_of(chunk, device)
        driven = policy.forward(features, navigation).ego_trajectory_se2[..., :2]
        e = (driven - trajectory[..., :2]).norm(dim=-1).mean(dim=-1).cpu().tolist()
        x = cross_track(driven.float(), path[..., :2].float()).cpu().tolist()
        errs += e
        xt += x
        is_off = [abs(s["lateral"]) > 0.3 for s in chunk]
        off += [v for v, o in zip(e, is_off) if o]
        xt_off += [v for v, o in zip(x, is_off) if o]
    nan = float("nan")
    return (float(np.mean(errs)), float(np.mean(off)) if off else nan, float(np.mean(xt)),
            float(np.mean(xt_off)) if xt_off else nan, len(off))


@hydra.main(config_path=str(CONFIG_PATH), config_name="evaluate_alpasim", version_base=None)
def main(cfg: DictConfig) -> None:
    setup_logging()
    seed = int(os.environ.get("CL_SEED", "0"))
    random.seed(seed), np.random.seed(seed), torch.manual_seed(seed)
    config = finalize_evaluation(cfg, AlpasimBenchmarkConfig, hydra_overrides())
    device = torch.device(config.device)
    policy = build_policy(config, device)
    timing = os.environ.get("CL_TIMING", "log")
    samples, skipped = load_samples(os.environ["CL_DATA"].split(":"), int(os.environ.get("CL_MAX_RECORDS", "0")), timing)
    LOG.info("label timing: %s", timing)
    scenes = sorted({s["scene"] for s in samples})
    val_frac = float(os.environ.get("CL_VAL_FRAC", "0.1"))
    val_scenes = {s for s in scenes if (zlib.crc32(s.encode()) % 1000) / 1000 < val_frac}
    train = [s for s in samples if s["scene"] not in val_scenes]
    val = [s for s in samples if s["scene"] in val_scenes]
    LOG.info("records: %d usable (%d skipped), %d scenes; train %d, val %d (%d scenes); off-log (|e| > 0.3 m) %d",
             len(samples), skipped, len(scenes), len(train), len(val), len(val_scenes),
             sum(abs(s["lateral"]) > 0.3 for s in samples))
    batch = int(os.environ.get("CL_BATCH", "32"))
    if val:
        LOG.info("val before: L1 all %.3f m, off-log %.3f m; cross-track all %.3f m, off-log %.3f m (n=%d)", *sampled_l1(policy, val, device, batch))

    policy.requires_grad_(False)
    policy.planning_decoder.requires_grad_(True)
    start = {k: v.detach().clone() for k, v in policy.planning_decoder.state_dict().items() if v.is_floating_point()}
    params = [p for p in policy.parameters() if p.requires_grad]
    weights = dict(policy.loss_weights(0))
    for name in filter(None, os.environ.get("CL_ZERO_LOSSES", "").split(",")):
        weights[name] = 0.0
    epochs = int(os.environ.get("CL_EPOCHS", "4"))
    steps = epochs * math.ceil(len(train) / batch)
    optimizer = torch.optim.AdamW(params, lr=float(os.environ.get("CL_LR", "2e-5")), weight_decay=0.01)
    scheduler = torch.optim.lr_scheduler.OneCycleLR(optimizer, max_lr=optimizer.param_groups[0]["lr"],
                                                    total_steps=max(steps, 1), pct_start=0.1)
    LOG.info("training %d params of the planning decoder, %d epochs, %d steps, weights %s",
             sum(p.numel() for p in params), epochs, steps, {k: round(float(v), 3) for k, v in weights.items() if v})
    step = 0
    for epoch in range(epochs):
        policy.eval()                     # frozen heads keep their batch-norm statistics
        policy.training = True            # _forward_heads' training-time conditioning (target point dropout)
        policy.planning_decoder.train()
        random.shuffle(train)
        running = []
        for i in range(0, len(train), batch):
            features, navigation, trajectory, path = batch_of(train[i: i + batch], device)
            total, losses = train_loss(policy, features, navigation, trajectory, path, weights)
            optimizer.zero_grad(set_to_none=True)
            total.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            optimizer.step()
            scheduler.step()
            step += 1
            running.append([float(total)] + [float(v) for v in losses.values()])
            if step % 50 == 0:
                LOG.info("epoch %d step %d/%d loss %s %s", epoch, step, steps, np.round(np.mean(running, 0), 4),
                         list(losses))
                running = []
        if val:
            LOG.info("val after epoch %d: L1 all %.3f m, off-log %.3f m; cross-track all %.3f m, off-log %.3f m (n=%d)", epoch,
                     *sampled_l1(policy, val, device, batch))
    moved = {k: float((v.detach() - start[k]).norm() / (start[k].norm() + 1e-12))
             for k, v in policy.planning_decoder.state_dict().items() if k in start}
    total_rel = math.sqrt(sum(float((v.detach() - start[k]).norm()) ** 2 for k, v in policy.planning_decoder.state_dict().items()
                              if k in start)) / math.sqrt(sum(float(t.norm()) ** 2 for t in start.values()))
    top = sorted(moved.items(), key=lambda kv: -kv[1])[:5]
    LOG.info("weights moved: decoder relative L2 %.4f; largest %s", total_rel, [(k, round(v, 4)) for k, v in top])
    out = os.environ["CL_OUT"]
    base = torch.load(config.policy_config.evaluation_checkpoint_files[0], map_location="cpu", weights_only=False)
    state = {k: v.detach().cpu() for k, v in policy.state_dict().items()}
    for k, v in base.items():                       # v0.2.0 files carry 4 constants the v0.2.2 model omits
        state.setdefault(k, v)
    torch.save({k: state[k] for k in base} | {k: v for k, v in state.items() if k not in base}, out)
    LOG.info("saved %s (%d tensors)", out, len(state))


if __name__ == "__main__":
    main()
