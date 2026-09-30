# alpasim-jepa ledger

## 2026-09-29 Why JEPA, and for which track
- **Current driver** (`../alpasim`, v0.3): Alpamayo 1.5 int8, no reasoning.
  - PAI: PCS 2143, rank 2/58.
  - nuPlan: PCS 1296, rank 19/71. The eligible teams ahead of us sit at ~1463-1469; the top 10 is mostly the host team py123d-garage.
- **Alpamayo is off-domain on nuPlan:** NVIDIA rig at 10 Hz vs the Motional rig at 2 Hz, and at-fault incident spacing 0.234 vs go-straight's 0.258.
- **Released JEPA planners are built for exactly the nuPlan contract** (NAVSIM: Motional cameras, 2 Hz, 8 waypoints at 0.5 s), with public weights. That keeps nuPlan prize eligibility (public data and weights only) and fits the Apache-2.0 submission terms.

| | WA-JEPA (arXiv 2608.20974) | Drive-JEPA (arXiv 2601.22032) |
|---|---|---|
| Idea | V-JEPA 2.1 ViT-L encoder + joint flow predictor that denoises future scene tokens AND the ego trajectory together (world-action model) | driving-video V-JEPA encoder + proposal-centric planner (multimodal trajectory distillation, momentum-aware selection) |
| Reported | NAVSIM v2.2 navtest EPDMS 91.7; HUGSIM 436-scenario zero-shot closed loop, HD-Score 0.4462 | NAVSIM v1 PDMS 93.3; v2 EPDMS 87.8 |
| Weights | Apache-2.0 (HF card) | CC0 (code Apache-2.0) |

## 2026-09-29 WA-JEPA input contract (from `configs/wa_jepa_navsim_epdms.yaml`, `eval/navsim_agent.py`, `close_loop/hugsim_planner.py`)
- **Model:** `variant: vjepa2_1_vit_large_384`, `camera_names: [cam_l0, cam_f0, cam_r0, cam_b0]` (order matters: learned per-slot camera embedding), `input_hw: [256, 512]`, `num_history_frames: 4`, `num_history_trajectory_steps: 4`, `trajectory_frame_rate_hz: 2.0`, `trajectory_horizon: 8`, `ego_status_dim: 8`. Flow predictor: 12 layers, 4 inference steps, `flow_inference_seed: 1`.
- **Images:** full frame (no crop), RGB, `cv2.resize` to 512x256 with INTER_AREA, scaled to [-1, 1]. Tensor `[T=4, V=4, 3, 256, 512]`, oldest first, 0.5 s apart.
- **Ego status:** `[command one-hot(4) (0 left, 1 straight, 2 right, 3 unknown), vx, vy, ax, ay]` in the ego frame. The command convention matches the organisers' `navigation.py`.
- **History trajectory:** the last 4 poses (x, y, yaw) relative to the current pose, x forward, y left.
- **Output:** `predict_trajectory` gives `[8, 3]` (x, y, yaw) at 0.5 s steps, ego frame.
- **Precision:** fp32 weights under bf16 autocast. The authors note that bf16 weights do NOT reproduce their numbers.
- **The authors' silent-failure checklist** (HUGSIM adapter): camera slot order, sample rate / history stride, world→ego frame, command encoding, output frame, precision.

## AlpaSim nuPlan-track mapping (to implement)
- **Cameras:** `CAM_L0, CAM_F0, CAM_R0, CAM_B0` (the track delivers 8 cameras at 1920x1080, 2 Hz). Drive calls come at the 0.5 s control step, so history stride = 1 frame.
- **Dynamics:** the RPC `DynamicState` (rig-frame velocity/acceleration), as in the organisers' sample. Pose history comes from egomotion observations.
- **Command:** `navigation.command_from_route` (the organisers' rule: first waypoint ≥5 m, lateral threshold 2 m). Caveat: the route starts 40 m ahead (`route_start_offset_m`).
- **Output:** 8 waypoints at 0.5 s go into the organisers' `trajectory.py` (rig → local frame, 10 Hz resampling, cached plan).
- **Budget:** a ViT-L encoder (~0.3B) + predictor is expected to be a few GB of GPU memory; to be measured against the 16 GiB cap and the nuPlan 3,000 s budget.

## Evaluation plan (approved by Aman 2026-09-29)
1. **Offline sanity:** run WA-JEPA / Drive-JEPA on nuPlan navtest frames; ADE/FDE vs human and vs Alpamayo.
2. **Local closed loop:** 100 nuPlan scenes, paired against Alpamayo v0.3 on the same scenes (`compare_runs.py`, bootstrap 90%), plus the failure taxonomy.
3. **If it clearly wins:** nuPlan-only image → nuplan-warmup → October slot.
4. **PAI:** JEPA as a candidate judge inside the full system (week 2 of `../alpasim/PLAN.md`).
- **Open:** where GPU work runs. Insomnia (our fair-share is 0.547; the sibling JEPA thread was told "no Insomnia, ask for RunPod") or RunPod. Ask Aman before any GPU job.

## 2026-09-29 Adapter built and smoke-tested (CPU, Mac)
- **Package `src/wajepa_challenge/`:** the organisers' NAVSIM sample (Apache-2.0, NVIDIA; see NOTICE.md) with `driver.py` modified plus our `preprocessing.py` and `policy.py`.
  - Driver: 4 cameras × 4-frame history (last 4 common frame times, oldest repeated early and counted as `history_pad`); pose history via `relative_se2`; frames resized to 256x512 on arrival; counters `model_inference` / `cached_plan` / `straight_fallback` / `dynamic_state_fallback` / `inference_error`.
  - Policy: WA-JEPA `build_world_model` + strict `load_checkpoint`; fp32 weights under bf16 autocast; the contract is checked against the checkpoint config.
- **Checkpoint load (CPU):** strict match; **788 M parameters** (ViT-L encoder + flow predictors, more than the ~0.3B assumed earlier), ~3.2 GB fp32. Load 14 s.
- **One CPU plan: 29 s** (says nothing about GPU speed). Random images, straight history at 5 m/s → the plan goes straight at ~4.6 m/s (x 2.35 → 14.9 m over 4 s, |y| ≤ 0.43 m), so the history, speed and frame conventions line up.
- **`tests/test_driver_history.py`** (simulated gRPC traffic, fake policy): 2/2 pass. History order and per-camera slots verified by pixel values; relative poses [-7.5, -5, -2.5, 0] m; ego status speed 5 m/s; Drive returns a forward trajectory; early-rollout padding counted.
- **Command finding:** the organisers' `command_from_route` looks at the first waypoint ≥5 m with a 2 m lateral threshold. With the route starting 40 m ahead, that almost always gives STRAIGHT (the organisers' NAVSIM samples share this). A later improvement candidate: a command from route heading vs the car, like alpasim nav v2.
- No bytecode was written into the read-only folders (`PYTHONDONTWRITEBYTECODE=1`; alpasim_grpc installed from a scratch copy).
- **Next (needs a GPU; compute location to be agreed with Aman):**
  1. GPU memory and latency per plan;
  2. offline sanity on nuPlan navtest frames;
  3. 100-scene local closed loop vs Alpamayo v0.3.
