"""WiSE-FT style weight averaging of two py123d_garage checkpoints of the same architecture.

out = (1 - alpha) * base + alpha * finetuned for every floating-point tensor; integer / bool tensors (counters, masks)
and non-tensor entries are taken from the base, as are tensors only the base holds (v0.2.0 files carry 4 planner
normalization constants that v0.2.2 checkpoints omit); a tensor only in the fine-tuned file is an error. The
averaged file keeps the base file's container layout, so py123d's evaluation loads it like a released checkpoint.

Usage: python wise_average.py BASE.pth FINETUNED.pth OUT.pth --alpha 0.5
"""
from __future__ import annotations

import argparse

import torch


def tensors(obj):
    """The state dict inside a checkpoint container (plain dict of tensors, or under 'state_dict' / 'model')."""
    if isinstance(obj, dict):
        for k in ("state_dict", "model", "policy"):
            if k in obj and isinstance(obj[k], dict):
                return obj[k], k
        if all(isinstance(v, torch.Tensor) for v in obj.values()):
            return obj, None
    raise ValueError(f"unrecognised checkpoint layout: {type(obj)} {list(obj)[:5] if isinstance(obj, dict) else ''}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("finetuned")
    ap.add_argument("out")
    ap.add_argument("--alpha", type=float, required=True, help="weight of the fine-tuned model (0 = base, 1 = fine-tuned)")
    a = ap.parse_args()
    base = torch.load(a.base, map_location="cpu", weights_only=False)
    ft = torch.load(a.finetuned, map_location="cpu", weights_only=False)
    sb, key = tensors(base)
    sf, _ = tensors(ft)
    ft_only = sorted(set(sf) - set(sb))
    assert not ft_only, f"tensors only in the fine-tuned file: {ft_only[:5]}"
    base_only = sorted(set(sb) - set(sf))   # py123d v0.2.0 files carry 4 planner normalization constants that v0.2.2
    n_avg = n_kept = 0                      # no longer saves (its strict load accepts both); they are kept from the base
    out = {}
    for k, vb in sb.items():
        if k in base_only:
            out[k] = vb.clone()
            n_kept += 1
            continue
        vf = sf[k]
        assert vb.shape == vf.shape, f"shape mismatch at {k}: {vb.shape} vs {vf.shape}"
        if vb.is_floating_point():
            out[k] = ((1 - a.alpha) * vb.float() + a.alpha * vf.float()).to(vb.dtype)
            n_avg += 1
        else:
            out[k] = vb.clone()
            n_kept += 1
    if key is None:
        result = out
    else:
        result = dict(base)
        result[key] = out
    torch.save(result, a.out)
    diff = max(float((sb[k].float() - sf[k].float()).abs().max()) for k in sf if sb[k].is_floating_point())
    print(f"averaged {n_avg} float tensors, kept {n_kept} others from the base; alpha {a.alpha}; "
          f"layout {'plain' if key is None else key!r}; base-only kept: {base_only}; max |base - finetuned| {diff:.4g} -> {a.out}")


if __name__ == "__main__":
    main()
