"""Open-loop check of the FlashDrive policy on real captured PAI driver inputs (alpasim data/ft_capture, read-only).

For N captured plans (frames, ego history, recorded 6.4 s future): FlashDrive's plan, and optionally the reference
v5 forced-start path on the original bf16 weights (Alpamayo15Policy, quant="none"; needs ~22 GB, so A6000-class
only). Reports latency per plan (after warm-up), peak memory (torch reserved and nvidia-smi for this process), the
ADE / FDE to the recorded future, and the FlashDrive-vs-reference plan distance.

Usage: python check_policy.py --samples DIR --n 40 [--reference] (env: A15_* paths as for the driver)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import time

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from a15_driver.capture import load_sample  # noqa: E402


def nvsmi_mib() -> int:
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True).stdout
    for line in out.strip().splitlines():
        pid, mem = [x.strip() for x in line.split(",")]
        if int(pid) == os.getpid():
            return int(mem)
    return -1


def run(policy, samples, label):
    plans, lat = [], []
    for i, path in enumerate(samples):
        frames, z = load_sample(path)
        hx = torch.from_numpy(z["hist_xyz"]).reshape(1, 1, -1, 3)
        hr = torch.from_numpy(z["hist_rot"]).reshape(1, 1, -1, 3, 3)
        torch.cuda.synchronize(); t0 = time.perf_counter()
        xy, yaw, _ = policy.predict(frames, [int(s) for s in z["slots"]], hx, hr)
        torch.cuda.synchronize(); dt = time.perf_counter() - t0
        if i >= 2:                                  # first two calls include compile / warm-up
            lat.append(dt)
        plans.append(xy)
        if i < 3:
            print(f"[{label}] call {i}: {dt * 1000:.0f} ms", flush=True)
    return np.stack(plans), np.array(lat)


def ade(a, b):
    n = min(a.shape[1], b.shape[1])
    d = np.linalg.norm(a[:, :n] - b[:, :n], axis=-1)
    return float(d.mean()), float(d[:, -1].mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", required=True)
    ap.add_argument("--n", type=int, default=40)
    ap.add_argument("--reference", action="store_true")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    samples = sorted(glob.glob(os.path.join(a.samples, "**", "*.npz"), recursive=True))
    step = max(1, len(samples) // a.n)
    samples = samples[::step][:a.n]
    gt = np.stack([np.load(p)["fut_xyz"].reshape(-1, 3)[:, :2] for p in samples])
    res = {"n": len(samples), "gpu": torch.cuda.get_device_name()}
    common = dict(model_dir=os.environ["A15_MODEL_DIR"], vlm_dir=os.environ["A15_VLM_DIR"],
                  processor_dir=os.environ["A15_PROCESSOR_DIR"])

    from a15_driver.flash_policy import FlashAlpamayo15Policy
    torch.cuda.reset_peak_memory_stats()
    t0 = time.time()
    fd = FlashAlpamayo15Policy(**common, paro_dir=os.environ["A15_PARO_DIR"],
                               compile_mode=os.environ.get("A15_FD_COMPILE", "max-autotune") or None)
    res["fd_load_s"] = round(time.time() - t0, 1)
    res["fd_mem_after_load_gib"] = round(torch.cuda.memory_reserved() / 2**30, 2)
    p_fd, lat = run(fd, samples, "flashdrive")
    res["fd_latency_ms"] = {"mean": round(lat.mean() * 1000, 1), "p50": round(np.median(lat) * 1000, 1),
                            "p90": round(np.percentile(lat, 90) * 1000, 1)}
    res["fd_peak_reserved_gib"] = round(torch.cuda.max_memory_reserved() / 2**30, 2)
    res["fd_nvidia_smi_mib"] = nvsmi_mib()
    res["fd_vs_recorded_ade_fde"] = ade(p_fd, gt)
    print(json.dumps(res), flush=True)

    if a.reference:
        del fd; torch.cuda.empty_cache()
        from a15_driver.policy import Alpamayo15Policy
        ref = Alpamayo15Policy(**{**common, "model_dir": os.environ["A15_REF_MODEL_DIR"]}, quant="none",
                               force_start=True, embed_cpu=True)
        p_ref, lat_r = run(ref, samples, "reference")
        res["ref_latency_ms_mean"] = round(lat_r.mean() * 1000, 1)
        res["ref_vs_recorded_ade_fde"] = ade(p_ref, gt)
        res["fd_vs_ref_ade_fde"] = ade(p_fd, p_ref)
        mv_fd = np.linalg.norm(p_fd[:, 39], axis=-1); mv_ref = np.linalg.norm(p_ref[:, 39], axis=-1)
        res["planned_4s_distance_m_mean"] = {"fd": round(float(mv_fd.mean()), 2), "ref": round(float(mv_ref.mean()), 2),
                                             "recorded": round(float(np.linalg.norm(gt[:, 39], axis=-1).mean()), 2)}
    print("RESULT " + json.dumps(res), flush=True)
    if a.out:
        np.savez(a.out, fd=p_fd, gt=gt, **({"ref": p_ref} if a.reference else {}))


if __name__ == "__main__":
    main()
