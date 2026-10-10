"""Route-conditioned WA-JEPA: a target-point input added to the released model without changing its code.

  * `TargetPointEncoder` (2 -> 512 -> 512, last layer zero-initialised) encodes the route point 45 m ahead (rear-axle
    frame, divided by 45 m). Its output is added to the ego-status token that WA-JEPA broadcasts to its 8 trajectory
    tokens, so at initialisation the model is exactly the released one.
  * The NAVSIM adapters are wrapped per instance: the trajectory adapter's `encode` adds the target-point term when
    the inputs carry "target_point"; the driving-condition adapter passes "target_point" through at inference.
  * Only trajectory-stream parameters and the new encoder train (`trainable_names`); the encoders, scene projector
    and the context/scene streams stay frozen, so cached features are exact inputs.
"""
from __future__ import annotations

import re
import types

import torch
from torch import nn
import torch.nn.functional as F

TARGET_SCALE_M = 45.0
_TRAJ_PARAM = re.compile(r"^predictor\.(noisy_traj_proj|history_traj_encoder|ego_status_encoder|traj_fusion|traj_out|"
                         r"traj_pos|traj_type_embed|target_point_encoder)(\.|$)|^predictor\.blocks\.\d+\.(traj_attn_norm|"
                         r"traj_ffn_norm|traj_ffn|joint_attn\.traj_\w+)(\.|$)")


class TargetPointEncoder(nn.Module):
    def __init__(self, hidden: int) -> None:
        super().__init__()
        self.net = nn.Sequential(nn.Linear(2, hidden), nn.GELU(), nn.Linear(hidden, hidden))
        nn.init.zeros_(self.net[2].weight)
        nn.init.zeros_(self.net[2].bias)

    def forward(self, target_point: torch.Tensor) -> torch.Tensor:
        return self.net(target_point / TARGET_SCALE_M)


def install(model) -> None:
    """Add the target-point encoder and wrap the two NAVSIM adapters of this model instance."""
    pred = model.predictor
    if hasattr(pred, "target_point_encoder"):
        return
    p0 = next(pred.parameters())
    pred.target_point_encoder = TargetPointEncoder(pred.hidden_dim).to(device=p0.device, dtype=p0.dtype)

    traj_adapter = pred.trajectory_adapter
    base_encode = traj_adapter.encode

    def encode(self, predictor, inputs, *, dtype):
        traj = base_encode(predictor, inputs, dtype=dtype)
        tp = inputs.get("target_point")
        if tp is None:
            return traj
        # traj_fusion is linear in the ego token, so adding the term to the fused output equals adding a vector
        # to the ego token: fusion(cat[a, h, e + d]) = fusion(cat[a, h, e]) + W_ego d.
        d = predictor.target_point_encoder(tp.to(dtype=dtype)).unsqueeze(1)
        w_ego = predictor.traj_fusion.weight[:, 2 * predictor.hidden_dim:]
        return traj + F.linear(d, w_ego).expand(-1, predictor.trajectory_horizon, -1)

    traj_adapter.encode = types.MethodType(encode, traj_adapter)

    cond = model.driving_condition_adapter
    base_inference = cond.inference_conditions

    def inference_conditions(self, batch):
        out = base_inference(batch)
        if isinstance(batch.get("target_point"), torch.Tensor):
            out.predictor_inputs["target_point"] = batch["target_point"]
        return out

    cond.inference_conditions = types.MethodType(inference_conditions, cond)


def trainable_names(model, only_target_point: bool = False) -> list[str]:
    names = [n for n, _ in model.named_parameters() if _TRAJ_PARAM.search(n)]
    return [n for n in names if n.startswith("predictor.target_point_encoder.")] if only_target_point else names


def freeze_all_but_trajectory(model, only_target_point: bool = False) -> list[nn.Parameter]:
    """only_target_point: train just the new target-point encoder (the released model cannot drift; the route
    signal is the only change)."""
    names = set(trainable_names(model))
    if only_target_point:
        names = {n for n in names if n.startswith("predictor.target_point_encoder.")}
    params = []
    for n, p in model.named_parameters():
        p.requires_grad_(n in names)
        if n in names:
            params.append(p)
    return params


def _common(model, bsz: int, device):
    masks = model.mask_sampler.full_future_mask(bsz, device=device)
    ctx_idx = model._history_indices_from_masks(masks.masks_x[0], bsz)
    return ctx_idx


def flow_loss(model, context_scene, target_scene, ego_status, history_trajectory, future_trajectory,
              target_point=None) -> torch.Tensor:
    """WA-JEPA's trajectory x-pred flow loss (`_flow_predict_groups` + `_trajectory_flow_loss`) on cached features."""
    from models.multiview_causal_future_jepa import DrivingConditionBatch
    bsz, device = context_scene.size(0), context_scene.device
    dtype = context_scene.dtype
    t = model._sample_flow_time(bsz, device=device, dtype=dtype)
    noisy_scene, _ = model._flow_interpolate(target_scene, t)
    inputs = {"ego_status": ego_status, "history_trajectory": history_trajectory}
    if target_point is not None:
        inputs["target_point"] = target_point
    flow = model.driving_condition_adapter.prepare_training_flow(
        model, DrivingConditionBatch(target_trajectory=future_trajectory, predictor_inputs=inputs),
        t_cont=t, dtype=dtype, device=device)
    _, pred_traj = model.predictor(
        context_scene=context_scene, context_token_indices=_common(model, bsz, device),
        noisy_future_scene=noisy_scene,
        future_condition_scene=model._future_mask_condition(bsz, device=device, dtype=dtype),
        t_cont=t, trajectory_inputs=flow.predictor_inputs)
    return F.mse_loss(pred_traj.float(), flow.clean_target.float())


@torch.no_grad()
def predict_from_cache(model, context_scene, ego_status, history_trajectory, target_point=None) -> torch.Tensor:
    """`predict_trajectory` from a cached `context_scene`: same seeded noise (scene first, then trajectory), same
    Euler steps. Returns [B, 8, 3] in metres/radians."""
    from models.multiview_causal_future_jepa import DrivingConditionBatch
    bsz, device = context_scene.size(0), context_scene.device
    dtype = context_scene.dtype
    inputs = {"ego_status": ego_status, "history_trajectory": history_trajectory}
    if target_point is not None:
        inputs["target_point"] = target_point
    cond = DrivingConditionBatch(predictor_inputs=inputs)
    gen, sample_device = model._make_inference_generator(device)
    scene = model._randn_for_inference((bsz, model.predictor.num_scene_tokens, model.scene_projector.scene_dim),
                                       device=device, dtype=dtype, generator=gen,
                                       sample_device=sample_device) * model.flow_inference_noise_scale
    traj = model.driving_condition_adapter.initial_inference_trajectory(
        model, bsz, device=device, dtype=dtype, generator=gen, sample_device=sample_device)
    tin = model.driving_condition_adapter.prepare_inference_inputs(model, cond, dtype=dtype, device=device)
    ctx_idx = _common(model, bsz, device)
    fcond = model._future_mask_condition(bsz, device=device, dtype=dtype)
    steps = max(model.flow_num_inference_steps, 1)
    dt = 1.0 / steps
    for step in range(steps):
        t = torch.full((bsz,), min(step / steps, 1.0 - 1e-4), device=device, dtype=dtype)
        tin["noisy_trajectory"] = traj
        pred_scene, pred_traj = model.predictor(context_scene=context_scene, context_token_indices=ctx_idx,
                                                noisy_future_scene=scene, future_condition_scene=fcond,
                                                t_cont=t, trajectory_inputs=tin)
        denom = (1.0 - t).clamp_min(1e-3).view(-1, 1, 1)
        scene = scene + dt * (pred_scene - scene) / denom
        traj = traj + dt * (pred_traj - traj) / denom
    return model.driving_condition_adapter.inference_output(model, traj)
