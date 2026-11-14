"""DAgger-style fine-tune of W1 (py123d v0.2.0 ltf-base-waypoints-68M posttrain model_1) on its own closed-loop states.

Samples come from `g2_dagger.entry` rollouts on training scenes (log-disjoint from every held-out scene we test on).
Each sample holds the model inputs at a state the policy itself reached and the human (logged) ego trajectory in the
rig frame of that state. The label is the human's future, blended from the current pose back onto the human's
trajectory over T_REC seconds (a recovery label):
    label(t0 + k dt) = H(t_ref + k dt) - (1 - w_k) * H(t_ref),  w_k = min(1, k dt / T_REC)
with H the human pose in the current rig frame, t_ref = t0 when the ego is within LAG_M of the human, else the time of
the human's closest pose (follow the human's path and pace from where the ego is, instead of racing to catch up).
Only the planning decoder trains (the released config freezes the backbone), with the released flow-matching loss.

Usage: python -m g2_dagger.train --data DIR [DIR ...] --ckpt W1/model_1.pth --out OUTDIR [--epochs 4 --lr 2e-5]
Writes OUTDIR/model_1.pth (+ config.yaml and sensor rigs copied from the W1 dir) and OUTDIR/train_log.json.
"""
from __future__ import annotations

import argparse
import dataclasses
import glob
import json
import os
import random
import shutil
import time

import numpy as np
import torch
from hydra import compose, initialize_config_dir

from py123d_garage.common.config_help import CONFIG_PATH, finalize_evaluation, register_schema
from py123d_garage.config.schema.evaluation.alpasim_config import AlpasimBenchmarkConfig
from py123d_garage.evaluation.alpasim.help.config_help import build_policy
from py123d_garage.policy.transfuser.network.decoder.flow_planning_decoder import _split_speed


def masked_flow_loss(dec, tokens: torch.Tensor, label: torch.Tensor) -> torch.Tensor:
    """The released flow-matching waypoint loss (FlowPlanningDecoder.compute_loss, waypoint head only), averaged over
    the label steps whose mask (label[..., 3]) is 1 instead of over all 64."""
    assert dec._action_config is None and not dec._num_path_points, "waypoint-only flow head expected"
    flow = dec._config.planning_config.flow_config
    draws = flow.num_noise_draws
    pose, mask = label[..., :3].float(), label[..., 3].float()
    context, _ = _split_speed(tokens)
    target = dec._pack((pose - dec.pose_mean) / dec.pose_scale, None, None).repeat_interleave(draws, dim=0)
    context = dec._noise_draw_context(context)
    pose, mask = pose.repeat_interleave(draws, dim=0), mask.repeat_interleave(draws, dim=0)
    noise_level = torch.rand(target.shape[0], device=target.device) ** (1.0 / flow.noise_level_beta_alpha)
    flow_time = torch.ones_like(noise_level) - noise_level
    noisy = flow_time[:, None, None] * target + noise_level[:, None, None] * torch.randn_like(target)
    velocity = dec._velocity(context, noisy, flow_time)
    clean, _, _ = dec._unpack(noisy + noise_level[:, None, None] * velocity)
    pred = clean * dec.pose_scale + dec.pose_mean
    err = (pred[..., :2] - pose[..., :2]).abs().mean(-1) + (pred[..., 2] - pose[..., 2]).abs()
    return (err * mask).sum() / mask.sum().clamp(min=1.0)

def served_plan(dec, tokens: torch.Tensor) -> torch.Tensor:
    """The plan the driver serves (FlowPlanningDecoder._integrate with noise_temperature 0: Euler steps from the zero
    state, one draw), with autograd on. Call with the decoder in eval mode, as _integrate runs it."""
    flow = dec._config.planning_config.flow_config
    assert flow.noise_temperature == 0.0 and flow.num_averaged_samples == 1, "deterministic sampling expected"
    assert dec._action_config is None and not dec._num_path_points, "waypoint-only flow head expected"
    context, _ = _split_speed(tokens)
    b = context.shape[0]
    state = torch.zeros((b, 1, dec._num_state_values), device=context.device, dtype=torch.float32)
    for step in range(flow.num_inference_steps):
        t = torch.full((b,), step / flow.num_inference_steps, device=state.device, dtype=state.dtype)
        state = state + dec._velocity(context, state, t) / flow.num_inference_steps
    wp, _, _ = dec._unpack(state)
    return wp * dec.pose_scale + dec.pose_mean


def served_loss(dec, tokens: torch.Tensor, label: torch.Tensor) -> torch.Tensor:
    """Masked L1 (xy mean + yaw, as pose_l1_loss) between the served plan and the label."""
    pred = served_plan(dec, tokens)
    pose, mask = label[..., :3].float(), label[..., 3].float()
    err = (pred[..., :2] - pose[..., :2]).abs().mean(-1) + (pred[..., 2] - pose[..., 2]).abs()
    return (err * mask).sum() / mask.sum().clamp(min=1.0)


def rollout_scores(run_glob: str) -> dict:
    """rollout_id (= driver session id) -> (scene, score) from every matching run's results-summary.json."""
    out = {}
    for p in glob.glob(os.path.join(run_glob, "aggregate", "results-summary.json")):
        for r in json.load(open(p)).get("rollouts", []):
            out[r["rollout_id"]] = (r["clipgt_id"], float(r.get("score") or 0.0))
    return out


DT_US = 100_000
N = 64
EXTRAP_US = 500_000
MIN_VALID = 15


def interp_traj(arr: np.ndarray, t_us: np.ndarray) -> np.ndarray:
    """(x, y, yaw) of the logged trajectory at times t_us; constant velocity past its ends."""
    ts = arr[:, 0]
    yaw = np.unwrap(arr[:, 3])
    out = np.stack([np.interp(t_us, ts, arr[:, 1]), np.interp(t_us, ts, arr[:, 2]), np.interp(t_us, ts, yaw)], 1)
    if len(ts) >= 2:
        hi = t_us > ts[-1]
        if hi.any():
            v = (arr[-1, 1:3] - arr[-2, 1:3]) / max(ts[-1] - ts[-2], 1)
            out[hi, :2] = arr[-1, 1:3] + (t_us[hi] - ts[-1])[:, None] * v
        lo = t_us < ts[0]
        if lo.any():
            v = (arr[1, 1:3] - arr[0, 1:3]) / max(ts[1] - ts[0], 1)
            out[lo, :2] = arr[0, 1:3] + (t_us[lo] - ts[0])[:, None] * v
    return out


def make_label(rec: dict, t_rec: float, lag_m: float) -> tuple[np.ndarray, dict] | None:
    arr = rec["gt"]
    if arr is None or len(arr) < 2:
        return None
    t0 = rec["gt_step_us"]
    h0 = interp_traj(arr, np.array([t0], dtype=np.float64))[0]
    info = {"off": float(np.hypot(h0[0], h0[1])), "lat": float(h0[1]), "lon": float(h0[0])}
    t_ref = t0
    if info["off"] > lag_m:
        # the human's closest pose to the ego, searched on a 0.1 s grid over the recording
        grid = np.arange(arr[0, 0], arr[-1, 0] + 1, DT_US, dtype=np.float64)
        p = interp_traj(arr, grid)
        t_ref = float(grid[np.argmin(np.hypot(p[:, 0], p[:, 1]))])
        info["shift_s"] = (t_ref - t0) / 1e6
    tk = t_ref + DT_US * np.arange(0, N + 1, dtype=np.float64)
    H = interp_traj(arr, tk)
    w = np.minimum(1.0, np.arange(0, N + 1) * 0.1 / t_rec)[:, None]
    lab = H - (1.0 - w) * H[0:1]
    info["ref_off"] = float(np.hypot(H[0, 0], H[0, 1]))
    # only the part of the label backed by the recording (+ EXTRAP_US of constant-velocity extrapolation) trains
    mask = (tk[1:] <= arr[-1, 0] + EXTRAP_US).astype(np.float32)
    info["valid"] = int(mask.sum())
    return np.concatenate([lab[1:], mask[:, None]], 1).astype(np.float32), info


def load_human(files, a, stats):
    samples = []
    for f in files:
        rec = torch.load(f, weights_only=False)
        lab = make_label(rec, a.t_rec, a.lag_m)
        if lab is None:
            stats["no_gt"] += 1; continue
        label, info = lab
        if info["off"] > a.max_off and info.get("ref_off", 0) > a.max_off:
            stats["far"] += 1; continue
        if info["valid"] < MIN_VALID:
            stats["short"] = stats.get("short", 0) + 1; continue
        stats["shifted"] += "shift_s" in info
        samples.append({"features": rec["features"], "navigation": rec["navigation"], "label": torch.from_numpy(label),
                        "pred": torch.from_numpy(rec["pred"]), "scene": rec["scene"], "info": info})
    return samples


def load_best(files, a, stats):
    """Reward-filtered self-imitation: per scene, the rollout with the highest scene score among the clean and noisy
    drives; its served plans are the labels (perturbed plans that led to a better drive teach the change, unperturbed
    ones anchor). Scenes whose clean drive is best (or within --margin) give anchor samples (label = own plan)."""
    scores = rollout_scores(a.runs)
    by_session = {}
    for f in files:
        sess = os.path.basename(f).split("__")[1]
        by_session.setdefault(sess, []).append(f)
    per_scene = {}
    for sess, fs in by_session.items():
        if sess not in scores:
            stats["unscored"] = stats.get("unscored", 0) + 1; continue
        scene, score = scores[sess]
        noisy = "_n0_" not in fs[0]
        per_scene.setdefault(scene, []).append((score, noisy, sess, fs))
    rng = random.Random(a.seed)
    samples, gains = [], []
    for scene, rolls in per_scene.items():
        clean = [r for r in rolls if not r[1]]
        if not clean:
            stats["no_clean"] = stats.get("no_clean", 0) + 1; continue
        c = clean[0][0]
        best = max(rolls, key=lambda r: (r[0], not r[1]))
        improved = best[1] and best[0] > c + a.margin
        if improved:
            chosen, kind = best, "improved"; gains.append(best[0] - c)
        elif rng.random() < a.anchor:
            chosen, kind = clean[0], "anchor"
        else:
            continue
        stats[kind] = stats.get(kind, 0) + 1
        for f in chosen[3]:
            rec = torch.load(f, weights_only=False)
            served = rec.get("served", rec["pred"])
            label = np.concatenate([served, np.ones((len(served), 1), np.float32)], 1)
            moved = float(np.abs(served - rec["pred"]).max())
            samples.append({"features": rec["features"], "navigation": rec["navigation"], "label": torch.from_numpy(label),
                            "pred": torch.from_numpy(rec["pred"]), "scene": rec["scene"],
                            "info": {"off": moved, "kind": kind}})
    stats["scenes_scored"] = len(per_scene)
    stats["gain_mean"] = float(np.mean(gains)) if gains else 0.0
    stats["perturbed_samples"] = sum(1 for x in samples if x["info"]["off"] > 1e-3)
    return samples


def cat(objs):
    o = objs[0]
    if o is None:
        return None
    if torch.is_tensor(o):
        return torch.cat(objs, 0)
    if dataclasses.is_dataclass(o):
        return dataclasses.replace(o, **{f.name: cat([getattr(x, f.name) for x in objs])
                                         for f in dataclasses.fields(o) if f.init})
    if isinstance(o, dict):
        return {k: cat([x[k] for x in objs]) for k in o}
    return o


def load_policy(ckpt: str, device: torch.device):
    register_schema("evaluate_alpasim", AlpasimBenchmarkConfig)
    d = os.path.dirname(ckpt)
    overrides = [f"policy_config.evaluation_checkpoint_files=[{ckpt}]",
                 f"policy_config.evaluation_sensor_rig_file={d}/sensor_rig_nuplan.yaml"]
    with initialize_config_dir(config_dir=str(CONFIG_PATH), version_base=None):
        cfg = compose(config_name="evaluate_alpasim", overrides=overrides)
    config = finalize_evaluation(cfg, AlpasimBenchmarkConfig, overrides)
    return build_policy(config, device)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", nargs="+", required=True)
    ap.add_argument("--ckpt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--t_rec", type=float, default=2.0)
    ap.add_argument("--lag_m", type=float, default=3.0)
    ap.add_argument("--max_off", type=float, default=6.0)
    ap.add_argument("--val_frac", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--loss", choices=["flow", "served"], default="served")
    ap.add_argument("--label", choices=["human", "best"], default="human",
                    help="human: recovery label from the log; best: the served plan of the best-scoring rollout per scene")
    ap.add_argument("--runs", default=os.environ.get("G2_RUNS", ""), help="glob of run dirs with results-summary.json (for --label best)")
    ap.add_argument("--margin", type=float, default=0.0, help="best rollout must beat the scene's clean rollout by more")
    ap.add_argument("--anchor", type=float, default=1.0, help="share of clean-best scenes kept as anchors (label = own plan)")
    a = ap.parse_args()
    random.seed(a.seed); torch.manual_seed(a.seed); np.random.seed(a.seed)
    dev = torch.device("cuda")
    t_start = time.time()

    files = sorted(f for d in a.data for f in glob.glob(os.path.join(d, "*.pt")))
    stats = {"files": len(files), "no_gt": 0, "far": 0, "shifted": 0}
    samples = load_human(files, a, stats) if a.label == "human" else load_best(files, a, stats)
    scenes = sorted({s["scene"] for s in samples})
    random.Random(a.seed).shuffle(scenes)
    val_sc = set(scenes[: max(1, int(len(scenes) * a.val_frac))])
    train = [s for s in samples if s["scene"] not in val_sc]
    val = [s for s in samples if s["scene"] in val_sc]
    offs = np.array([s["info"]["off"] for s in samples])
    stats.update(samples=len(samples), train=len(train), val=len(val), scenes=len(scenes),
                 off_median=float(np.median(offs)), off_p90=float(np.percentile(offs, 90)))
    print(json.dumps(stats), flush=True)

    policy = load_policy(a.ckpt, dev)
    for p in policy.parameters():
        p.requires_grad_(False)
    params = list(policy.planning_decoder.parameters())
    for p in params:
        p.requires_grad_(True)
    print(f"trainable {sum(p.numel() for p in params)/1e6:.1f}M of {sum(p.numel() for p in policy.parameters())/1e6:.1f}M", flush=True)
    opt = torch.optim.AdamW(params, lr=a.lr, weight_decay=0.01)

    def batches(rows, bs, shuffle):
        idx = list(range(len(rows)))
        if shuffle:
            random.shuffle(idx)
        for i in range(0, len(idx), bs):
            b = [rows[j] for j in idx[i:i + bs]]
            yield (cat([x["features"] for x in b]).to(dev), cat([x["navigation"] for x in b]).to(dev),
                   torch.stack([x["label"] for x in b]).to(dev), torch.stack([x["pred"] for x in b]).to(dev))

    def evaluate(rows):
        policy.eval(); tot = n = base = 0.0
        with torch.no_grad():
            for f, nv, lab, pred in batches(rows, 64, False):
                out = policy.forward(f, nv).ego_trajectory_se2.float()
                m = lab[..., 3]
                tot += ((out[..., :2] - lab[..., :2]).norm(dim=-1) * m).sum(-1).div(m.sum(-1)).sum().item()
                base += ((pred[..., :2] - lab[..., :2]).norm(dim=-1) * m).sum(-1).div(m.sum(-1)).sum().item()
                n += len(lab)
        return tot / max(n, 1), base / max(n, 1)

    # check: the differentiable served plan reproduces the driver's sampler (and the recorded plan)
    policy.eval()
    f, nv, lab, pred = next(batches(val or train, 16, False))
    with torch.no_grad():
        sampled = policy.forward(f, nv).ego_trajectory_se2.float()
    with torch.enable_grad():
        unrolled = served_plan(policy.planning_decoder, policy.forward(f, nv).trajectory).detach()
    check = {"unrolled_vs_sampled_m": float((unrolled[..., :2] - sampled[..., :2]).norm(dim=-1).max()),
             "sampled_vs_recorded_m": float((sampled[..., :2] - pred[..., :2]).norm(dim=-1).max())}
    print("check", json.dumps(check), flush=True)
    log = {"args": vars(a), "stats": stats, "check": check, "epochs": []}
    ade, ade_w1 = evaluate(val)
    print(f"epoch 0 val ADE {ade:.3f} m (W1 as recorded {ade_w1:.3f})", flush=True)
    log["epochs"].append({"epoch": 0, "val_ade": ade, "w1_recorded_ade": ade_w1})
    for ep in range(1, a.epochs + 1):
        # backbone stays in eval (frozen BatchNorm statistics); the flow loss trains the decoder with its dropout as
        # released, the served loss runs it in eval as the driver does
        policy.eval(); tl = []; t0 = time.time()
        if a.loss == "flow":
            policy.planning_decoder.train()
        for f, nv, lab, _ in batches(train, a.bs, True):
            pr = policy.forward(f, nv)
            fn = masked_flow_loss if a.loss == "flow" else served_loss
            loss = fn(policy.planning_decoder, pr.trajectory, lab)
            opt.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0); opt.step(); tl.append(loss.item())
        ade, _ = evaluate(val)
        print(f"epoch {ep} train loss {np.mean(tl):.4f} val ADE {ade:.3f} m ({time.time()-t0:.0f} s)", flush=True)
        log["epochs"].append({"epoch": ep, "train_loss": float(np.mean(tl)), "val_ade": ade})

    os.makedirs(a.out, exist_ok=True)
    policy.eval()
    torch.save(policy.state_dict(), os.path.join(a.out, "model_1.pth"))
    d = os.path.dirname(a.ckpt)
    for name in ("config.yaml", "sensor_rig_nuplan.yaml", "sensor_rig_nurec.yaml"):
        if os.path.exists(os.path.join(d, name)):
            shutil.copy(os.path.join(d, name), os.path.join(a.out, name))
    log["minutes"] = (time.time() - t_start) / 60
    json.dump(log, open(os.path.join(a.out, "train_log.json"), "w"), indent=1)
    print("saved", a.out, flush=True)


if __name__ == "__main__":
    main()
