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

## 2026-09-29 Insomnia setup (Aman: option A, use Insomnia)
- **Cluster folder** `/insomnia001/depts/edu/users/au2327/alpasim-jepa`:
  - `ext/WA-JEPA` @ bec2966 (git clone);
  - `weights/wa-jepa/model_state_dict.pt` from HF `AFARI-Research/WA-JEPA` @ 15c0770e, sha256 `e1d3be01…6408`, identical to the local copy smoke-tested on the Mac;
  - `envs/overlay`: opencv-python-headless 4.12.0.88 and timm 0.9.16 (V-JEPA's `models/utils/modules.py` imports timm).
- **Borrowed read-only** (BORROWED.md):
  - nureasoning `ext/a15env` (torch 2.8 cu128, omegaconf, einops);
  - alpasim `envs/overlay_driver` (grpc 1.84, protobuf 4.25.9, alpasim_grpc 0.54);
  - alpasim simulator sandboxes and nuPlan data;
  - alpasim summary/compare scripts (executed, not modified).
- **Our launcher copy** (`src/compose_apptainer.py`) mounts every bind under the alpasim tree read-only and refuses to create anything there. The wizard runs with `-B alpasim:ro`; all outputs, caches and `defines.filesystem` live under alpasim-jepa.
- **Baseline for pairing:** alpasim v0.3 nuPlan bench run `local_nuplan_a15_bench_12991555`. 100 scenes, 82 passed, mean scene score **0.759**; at-fault collision 0.03, offroad 0.06, left corridor 0.11, progress 0.85, dist-to-gt 1.80 m; 1000 Drive calls, mean 0.41 s.
- **Jobs:** GPU memory/latency check (L40S), then the 100-scene closed loop on the same scene list (dependency afterok).
- **GPU check** (job 12994593, L40S, driver 550.54): WA-JEPA per plan **0.202 s** at batch 1 (p90 0.203); 0.408 s at batch 2 (no batching gain). nvidia-smi process memory **6,114 MiB** (peak reserved 5.47 GiB).
  - Compare Alpamayo v0.3: 0.83 s / ~14.5-15 GB. So there's >10 GB headroom under the 16 GiB cap.
  - Sample plan matches the CPU run to within a few cm (bf16 autocast vs fp32).

## 2026-09-29 Closed loop: WA-JEPA vs Alpamayo v0.3, same 100 nuPlan scenes (job 12994594, L40S, 22m39s)
- **Run:** `runs/nuplan_wajepa_v1_12994594`. Scene list copied from `local_nuplan_a15_bench_12991555` (navtest assets), 2 concurrent rollouts as officially. Command rule: the organisers' `command_from_route`, unchanged.

| | Alpamayo v0.3 | WA-JEPA v1 |
|---|---|---|
| Mean scene score | 0.759 | **0.958** |
| Passed | 82 | **96** |
| At-fault collision | 0.03 | **0.00** |
| Offroad | 0.06 | 0.03 |
| Left corridor | 0.11 | 0.01 |
| Progress | 0.85 | 0.98 |
| Dist to GT | 1.80 m | 1.01 m |
| Drive call (mean) | 0.41 s | 0.215 s |
| Driver GPU memory | ~14.5-15 GB | 5.4 GB |

- **Paired:** +0.198, 90% bootstrap [+0.131, +0.265]; wins 35, losses 2, ties 63. The noise we saw on a same-config rerun was ±0.03 at 40 scenes, so this is far outside it.
- **Taxonomy** (first failure category): baseline 63% clean pass, 19% low progress, 9% corridor, 6% offroad, 3% collision. WA-JEPA 93% clean pass, 3% low progress, 3% offroad, 1% corridor, 0% collision. 35 scenes change category.
- **Driver health:** 1000 Drive calls, all `model_inference` (10 per scene); 0 cached, 0 straight fallback, 0 dynamic-state fallback, 0 inference errors. Load 7 s, warm-up peak reserved 4.82 GiB.
- **Caveats:**
  - 100 local navtest scenes are not the hidden test set. The baseline scored 0.759 locally, and its official nuPlan PCS was 1296 (rank 19/71).
  - WA-JEPA's README states the navtest EPDMS eval; training is on navtrain (the NAVSIM protocol), so these scenes should be held out. Not verified from their training config.
- **Next:** a nuPlan-only image with WA-JEPA, then a nuplan-warmup and an October slot. Needs Aman.

## 2026-09-29 Validation of the WA-JEPA result (Aman: "check again rigorously")
**Checks without new runs:**
- **Config parity:** the wizard/eval/controller/trafficsim/driver configs of the baseline and WA-JEPA runs are identical apart from paths, ports and video rendering. The renderer logs are the same length with the same warnings. Results are independent runs: different run uuids, no shared rollout ids.
- **Scene diversity (weakness):** the 100 shard-001 scenes come from only 4 logs / 11 segments (66 from one log). The AlpaSim local pool is only these 100 (38 GB); navtest has 1491 scene configs over 44 logs.
- **No train/test overlap:**
  - All 4 shard-001 logs are in NAVSIM `navtest.yaml` and absent from `navtrain.yaml` (checked against autonomousvision/navsim main).
  - WA-JEPA fine-tunes on navtrain (`causal_future_jepa_mv_navsim.yaml`). Its stage-1 video pretraining uses nuPlan `splits/train`. navtest logs come from nuPlan's test split.
- **Official preset** (`e2e_challenge_nuplan_common/base.yaml`, shared by dev and ec2): all 8 cameras including CAM_B0 at 1920x1080 / 0.5 s, so WA-JEPA's rear camera is delivered officially. The organisers' guide mentions only L0/F0/R0 because their samples use 3.
- **Upstream `e2e_challenge`** is still at 2023534, so nothing changed since our pin.
- **The baseline is the submitted v0.3 config** (`A15_INFERENCE_INTERVAL_US=1000000`, as verified inside the image, Result 8 of the alpasim ledger).
- **Per segment** (shard 001): WA-JEPA is better on 10 of 11 segments and tied on 1. Its wins came from baseline low progress (19), corridor (8), offroad (5) and collision (3). Its 2 losses were offroad.

**New runs** (L40S; `runs/nuplan_*`):

| Run | Scenes | Mean score | Passed | vs Alpamayo v0.3, same scenes |
|---|---|---|---|---|
| WA-JEPA v1 (12994594) | shard 001 | 0.958 | 96 | +0.198 [+0.131, +0.265], 35 W / 2 L |
| WA-JEPA rerun, video + frame dumps (12994800) | shard 001 | 0.958 | 96 | identical to v1 on all 100 scenes (deterministic) |
| WA-JEPA, cameras blanked to grey (12994801) | shard 001 | 0.392 | 44 | -0.368 |
| Constant velocity, no model (12994802) | shard 001 | 0.578 | 74 | -0.181 |
| **Alpamayo v0.3** (12994804) | **shard 010** (new logs) | 0.510 | 58 | |
| **WA-JEPA** (12994803) | **shard 010** | **0.729** | **75** | **+0.219 [+0.123, +0.312], 41 W / 11 L** |

- **It uses the cameras:** blanking them drops the score from 0.958 to 0.392.
- **The scenes are not trivial:** keeping constant velocity scores 0.578.
- **Held-out shard 010** (4 other logs, 2021-09-16, 8 segments): the gain holds (+0.22), and WA-JEPA is better on 7 of 8 segments. Absolute scores are lower on this shard for both drivers, so shard 001 is an easy shard; local absolute numbers depend heavily on scene mix.
  - Failures: Alpamayo offroad 30, corridor 5, collision 4. WA-JEPA offroad 15, corridor 5, collision 2.
  - 3 scenes fail for both drivers on a simulator route sanity check ("route folds back on itself").
  - 8 of WA-JEPA's offroad failures have dist_to_gt < 0.6 m (it follows the recorded path and is still offroad). Possibly map artifacts; not investigated.
- WA-JEPA's driver process uses 5,442 MiB of GPU memory in every run; plans take 0.22 s each.

## 2026-09-30 WA-JEPA vs the organisers' SimScale sample drivers (the field's easy baseline)
The organisers ship NAVSIM sample images (checkpoints from `OpenDriveLab/SimScale`) that any team can submit. Here they run read-only from the upstream checkout, with the env of their Dockerfiles except torch 2.8 (vs 2.6) and opencv 4.12 (vs 4.9, numpy 2).
- The GTRS vocabulary in our checkout was a git-lfs pointer; the real object (sha256 `e8c29cfc…`) was fetched from GitHub media.

| Driver | Shard 001 (easy) | Shard 010 (held out) | Mean of both |
|---|---|---|---|
| **WA-JEPA** | **0.958** (96) | 0.729 (75) | **0.844** |
| LTF (SimScale) | 0.907 (93) | 0.700 (73) | 0.804 |
| DiffusionDrive (SimScale) | 0.853 (88) | 0.690 (72) | 0.772 |
| GTRS-Dense ResNet reward (SimScale) | 0.813 (82) | **0.730** (73) | 0.772 |
| Alpamayo v0.3 (ours, submitted) | 0.759 (82) | 0.510 (58) | 0.635 |

- **Paired, WA-JEPA minus each sample:**
  - Shard 001: LTF +0.051 [0.000, +0.101]; DiffusionDrive +0.105 [+0.050, +0.161]; GTRS +0.145 [+0.082, +0.212].
  - Shard 010: LTF +0.029 [-0.059, +0.114]; DiffusionDrive +0.039 [-0.049, +0.126]; GTRS -0.001 [-0.086, +0.082].
- **Reading:** WA-JEPA's big gain is over OUR Alpamayo entry (off-domain on nuPlan), not over the field. On held-out logs it is level with the organisers' samples. Teams above us (~1463-1469) plausibly run these samples, so WA-JEPA alone likely lands among them rather than clearly ahead.
- **Headroom from complementarity** (per-scene oracle: best of the drivers):

| Oracle best of | Shard 001 | Shard 010 |
|---|---|---|
| WA-JEPA + GTRS | 0.979 | 0.868 |
| WA-JEPA + LTF | 0.990 | 0.862 |
| WA-JEPA + LTF + GTRS | 1.000 | 0.894 |

  - The drivers fail on different scenes (vs GTRS on shard 010: 16 wins / 16 losses). A runtime selector that recovered part of the +0.14 oracle gap would separate us from the field. Candidate: WA-JEPA and GTRS trajectories scored by GTRS's learned PDM-style reward head.
  - 9 shard-010 scenes fail for every driver (3 are simulator route-sanity errors).
- **Official reference:** Alpamayo v0.3 scored 0.827 mean scene score on the official 1000-scene nuPlan set. Local shards bracket it (0.759 and 0.510), so the official mix is between our two shards or easier.
- **Slots:** all 3 September official slots are used. October gives 3 (deadline 2026-10-31); 2 nuplan-warmups remain in the rolling 30 days (1 used on Sep 27).

## 2026-09-30 Rules check: is a WA-JEPA nuPlan submission allowed? (Aman asked)
Sources: the challenge Space (`nvidia/AlpasimE2EClosedLoopChallenge2026` @ 04a5278, sections 03-05), the contestant guide (`e2e_challenge/README.md` @ 2023534), the GitHub issues (#123, #157, #182, #184, #188, #189, #191) and the model/dataset cards.
- **Permitted resources:** "Award-eligible nuPlan submissions may use only publicly available datasets, annotations, and model weights."
  - WA-JEPA weights are public (HF, not gated, Apache-2.0). They were trained on public NAVSIM/nuPlan data, starting from public V-JEPA 2.1.
  - #184 (organiser): "data derived from public data is considered public", including generated rollouts from the provided nuPlan test split. So fine-tuning on public or derived data would also stay eligible.
- **Evaluation integrity:** the driver uses only what the RPC delivers at runtime (cameras, ego pose/dynamics, route). There are no hidden identifiers. The nuPlan test set is private (Space; #191: "unpublished anywhere", distribution close to public), so local navtest runs are development only.
- **Licence:** the terms (#188) require submissions under Apache-2.0 plus a broad licence to NVIDIA; Aman accepted `official-2026-08` on 2026-09-27.
  - WA-JEPA code is Apache-2.0 and the bundled V-JEPA 2 code is MIT (LICENSE files ship in the image). The weights are Apache-2.0 (HF card). All are compatible.
  - The organisers' sample code (Apache-2.0) and SimScale checkpoints (Apache-2.0) are compatible too, for the GTRS-scorer idea.
- **Container contract:**
  - ≤40 GiB image (ours 5.4 GB);
  - ≤16 GiB VRAM per replica (5.4 GB measured);
  - read-only root, /tmp 2 GiB, no network (smoke-tested with `--read-only`, non-root);
  - evaluation GPU is an H100 (#189). "Target 0.1 s of model work per Drive call" is enforced as a per-track throughput budget, not per call. v0.3 at 0.41 s/call used 1,268 of 3,000 s; WA-JEPA is 0.22 s/call on L40S.
- **Harmonizer** (Space: enabled for final reruns of top policies): an NRE (PAI renderer) option (`e2e_challenge/ec2.yaml`), so it does not affect the nuPlan/MTGS track.
- **Server code:** the deployment runs 0bb4c4b. Our local pin 2023534 differs only in the CLI/README (warmup track, allocation message).
- **Reporting:** award eligibility needs a final valid submission plus a 4-page technical report. The report must credit WA-JEPA (AFARI-Research) and the organisers' adapter as the basis.
- **Not read:** the terms text itself is private and only shown by the CLI (`alpasim_challenge.py terms show`). Our knowledge of it comes from #188 and Aman's acceptance.

## 2026-09-30 Submission image verified in the local closed loop
- **Image** `alpasim-jepa/wajepa:dev` (Docker id `sha256:2a5b22e5…`, 5.38 GB, built from commit e134b4c + the opencv fix; container/Dockerfile.wajepa), run as an apptainer sandbox from `docker save` (job 12996546, L40S): **0.958 (96 passed), identical to native WA-JEPA v1 on all 100 shard-001 scenes** (100 ties).
  - Driver process 5,442 MiB (the first GPU pid, present before the simulator). Load 8 s; warm-up peak reserved 4.82 GiB.
  - 10 inferences per scene; 0 fallbacks and 0 errors.
- **Mac smoke test:** `--read-only --tmpfs /tmp --tmpfs /run`, uid 10001: imports and write dirs OK.
- **Apptainer-only harness issues** (not the image):
  - apptainer replaces the image HOME with the host home, and `--env HOME` is ignored, so the driver is launched via `env HOME=/tmp/home`;
  - Slurm's TMPDIR (/local/slurm-job-N) is invisible in containers, so the simulator stack runs with TMPDIR=/tmp.
- **Before a real submission:** rebuild from a clean commit so `WAJEPA_GIT_HASH` names it (dev build: e134b4c), then push to ECR (Aman).

## 2026-09-30 Zero-shot WA-JEPA on the PAI track (Aman: "measure it on PAI")
- **Setup:**
  - `WAJEPA_RIG=pai`: NVIDIA cameras mapped onto WA-JEPA's nuPlan slots. `crop` = FOV-matched crops: front centre 0.53 x 0.57, cross-left right part, cross-right left part. `resize` = full 120-degree frames. The rear slot is grey.
  - History: 4 frames 0.5 s apart picked from the 10 Hz stream. A new plan every 0.5 s, cached in between.
  - Same 40 curated-val scenes as the AlpaSim v0.3 bench run `local_pai_a15_bench1_12991558` (4 rollouts per replica, RTX PRO 6000 Blackwell).
  - Scene files read through symlinks into the AlpaSim data, bound read-only.
- **Results** (jobs 12996625 / 12996626):

| Driver | Mean scene score | Passed | vs Alpamayo v0.3 (paired) |
|---|---|---|---|
| Alpamayo v0.3 (main line) | 0.668 | 31/40 | |
| WA-JEPA, crop | 0.250 | 21/40 | -0.418 [-0.559, -0.267], 6 W / 30 L |
| WA-JEPA, resize | 0.301 | 17/40 | -0.368 [-0.512, -0.217], 4 W / 24 L |

- **Failures (crop):** offroad 9, corridor 8, collision 2; progress 0.33. It drives slowly and loses the lane on the unfamiliar rig.
- **Driver health:** 40 plans per scene, 0 fallbacks, 0 errors, 6,280 MiB. The adapter works; the model doesn't transfer.
- **Oracle best of Alpamayo + WA-JEPA:** 0.762 (+0.094; +0.131 with both views). WA-JEPA is better on 6 of 40 scenes. A selector would have to spot those few scenes against a much weaker second driver, so this is a low-priority idea for the main line's chooser, not a plan.
- **Conclusion:** as predicted, zero-shot WA-JEPA is far below Alpamayo on PAI. The track split stands: PAI stays on the Alpamayo line, and nuPlan moves to WA-JEPA.

## 2026-09-30 Terms text read (official-2026-08, sha256 8166fed2…; Aman ran `terms show`)
- **§3:** "The nuPlan track restricts teams to use any publicly available data to develop their policies". WA-JEPA and its training data are public. The same section says "participants are responsible for complying with any applicable terms of datasets used".
- **§5:** submissions must be under Apache-2.0 **with the licence notice included**. (b) The contestant represents that third-party components are Apache-2.0-compatible "and have been properly identified".
  - WA-JEPA code and weights are Apache-2.0, V-JEPA 2 is MIT (+Apache), and the NVIDIA adapter and alpasim_grpc are Apache-2.0: all compatible.
  - **Gap found and fixed:** the dev image had no top-level licence/notice. Added `container/LICENSE` (Apache-2.0 text) and `container/NOTICE` (every third-party component with source, revision and licence), copied to `/app/`. The next build carries them.
- **§8(c)/§13:** no third-party IP infringement. Removal is possible on a third-party IP claim.
  - The residual grey area is nuPlan's CC BY-NC-SA licence versus the commercial rights §5 grants NVIDIA over weights trained on it. It is shared by the organisers' own Apache-2.0 SimScale samples (nuPlan-trained) and every NAVSIM-based team. We cannot resolve it; the only remedy named is removal/disqualification of the Submission.
- **§2:** eligibility (age, jurisdiction, not an NVIDIA employee or family): Aman's to confirm; nothing here is JEPA-specific.

## 2026-09-30 New JEPA driving papers checked (Aman shared AD-E2E-JEPA)
- **AD-E2E-JEPA** (arXiv 2609.34085, 2026-09-28; Zhu, Zhang, LeCun, Choromanska):
  - Zero-shot planning needs **ground-truth future observations as goals**, which is unavailable at evaluation (rules: no information unavailable to the policy), so it is unusable in the challenge.
  - Scores: 72.9 EPDMS zero-shot; 85.4 as imitation learning with its projector (vs WA-JEPA 91.7).
  - The repo (HaoranZhuExplorer/AD-E2E-JEPA) holds only a README and images: no code, weights or licence.
  - Its 16x/4x compressed features (256 candidate rollouts in 0.8 s) are the right kind of tool for candidate scoring, but it needs a goal or a learned scorer. Watch only.
- **Auto-JEPA** (arXiv 2607.29031, 2026-07-31): NAVSIM v1 91.3 PDMS, v2 89.1 EPDMS (WA-JEPA 91.7). No code or weights mentioned. Watch only.

## Plan (agreed 2026-09-30/10-01)
- **Scope:** this thread owns nuPlan (WA-JEPA). The AlpaSim main line owns PAI (Alpamayo).
- **Slots:** October slots: PAI up to 2, nuPlan 1 (Aman; suggested deciding slots 2-3 mid-October on evidence).
- **nuPlan, one official slot:** submit around Oct 20-24 with the best locally validated system. Plain WA-JEPA is the fallback, and every add-on must beat it on held-out scenes.
  - Warmup 1 (plain WA-JEPA, early October) and warmup 2 (exact final image) first.
- **Next work:**
  - nuPlan leaderboard paste from Aman, for calibration against the host's sample-driver entries;
  - stream more navtest shards (download, run, delete);
  - WA-JEPA + GTRS scorer;
  - route-to-command rule;
  - frozen-encoder fine-tune pilot on Insomnia;
  - rebuild the image from a clean commit (LICENSE/NOTICE included) and push (Aman).

## 2026-10-01 GTRS judge for WA-JEPA plans, round 1 (global switching)
- **Judge** (`src/wajepa_challenge/judge.py`, GTRS-Dense ResNet reward vendored from the NVIDIA sample @ 2023534):
  - WA-JEPA's plan (resampled 8 → 40 poses) is appended to the 16,384-path vocabulary.
  - Score s = log NC + log DAC + 3 log EP (sigmoids).
  - GTRS's pick uses the sample's speed reranking. Drive GTRS's pick if s(GTRS) - s(WA-JEPA) > margin.
- **CPU checks:** strict load under timm 0.9.16. The GTRS pick equals the sample's own forward pick. GTRS's pick appended as the extra candidate scores -1.4782 vs -1.4772 in-vocabulary.
- **Closed loop**, paired against WA-JEPA on the same scenes (judge adds ~1 GB GPU):

| Margin | Switched plans | Shard 001 (WA-JEPA 0.958) | Shard 010 (WA-JEPA 0.729) |
|---|---|---|---|
| inf (log only) | 0% | 0.958, identical | 0.729, identical |
| 0 | 91-95% | 0.773 (-0.185 [-0.261, -0.112]) | 0.750 (+0.021 [-0.063, +0.108]) |
| 2 | 18-22% | 0.891 (-0.067 [-0.124, -0.012]) | **0.805 (+0.077 [+0.029, +0.128])** |

- **Mechanism** (scene outcome changes at margin 2):
  - Switching rescues offroad scenes (3 on 001, 6 on 010) and corridor scenes (3 on 010).
  - It creates corridor exits (6 on 001) and a few collisions. GTRS does not follow the route, so its picks drift off the recorded route.
- **Next:** radius-limited judge. GTRS may only choose paths within R m of WA-JEPA's path (keeps route intent, allows safety/speed corrections). Runs (R, margin) = (1, 1), (2, 1), (2, 2) on both shards (13062081-86).
  - The winner must then confirm on fresh shard 005 (fetch 13062087), since two configs were tuned on shards 001/010.

## 2026-10-01 GTRS judge, round 2: radius-limited local correction
- GTRS may only pick vocabulary paths within R m of WA-JEPA's path at every 0.1 s pose (best NC*DAC*EP^3 inside the radius). WA-JEPA's plan is replaced if s(pick) - s(WA-JEPA) > margin.

| R, margin | Switched | Shard 001 (WA-JEPA 0.958) | Shard 010 (WA-JEPA 0.729) |
|---|---|---|---|
| **1, 1** | 22% / 14% | **0.989** (99 passed) **+0.032 [+0.010, +0.061]**, 5 W / 0 L | **0.776 +0.047 [+0.008, +0.095]**, 7 W / 6 L |
| 2, 1 | 28% / 21% | 0.914 -0.044 [-0.095, +0.007] | 0.794 +0.065 [+0.016, +0.120] |
| 2, 2 | 17% / 13% | 0.949 -0.008 [-0.054, +0.032] | 0.796 +0.067 [+0.020, +0.118] |

- **R=1, margin=1 is the only setting positive on both shards.** It was chosen among 3 (+2 global) settings on these same shards, so it must confirm on the untouched shard 005.
  - Shard 005: 100 scenes, 5 logs (2021-06-28, 2021-08-16, 2021-08-30); scene list in `runs/scenes_shard005`.
  - Runs: WA-JEPA 13062857, judge R1 m1 13062858, LTF 13062859, GTRS 13062860.

## 2026-10-01 Warmup-ready image: `alpasim-jepa/wajepa:v1-4662979` (plain WA-JEPA)
- Built from clean commit 4662979 (Docker id `sha256:53019680…`, 5.38 GB). It carries /app/LICENSE (Apache-2.0) and /app/NOTICE (all third-party components) per terms §5; the driver reports git_hash 4662979.
- Local closed loop (job 13062216, apptainer sandbox of the docker archive): **0.958, identical to native WA-JEPA on all 100 shard-001 scenes.**
- The judge is off by default in this image (`WAJEPA_JUDGE` unset); the GTRS weights are not included. A judge image would be a separate build.
- **Next (Aman):** tag and push to ECR as `teams/amanupg:<tag>`, then submit a **nuplan-warmup** (not an official slot).

## 2026-10-01 Judge (R=1, margin 1) confirmed on the untouched shard 005; pooled 300 scenes
- **Shard 005** (100 scenes, 5 logs not used for any choice):

| Driver | Mean | Passed |
|---|---|---|
| WA-JEPA | 0.944 | 95 |
| **WA-JEPA + GTRS judge** | **0.985** | **99** |
| LTF | 0.900 | 92 |
| GTRS | 0.886 | 89 |

  - Judge vs WA-JEPA: +0.041 [+0.001, +0.081], 6 W / 2 L.
- **Pooled over shards 001 + 010 + 005** (300 scenes, 17 logs; paired bootstrap 90%):
  - Means: judge 0.917, WA-JEPA 0.877, LTF 0.836, GTRS 0.810.
  - Judge - WA-JEPA: +0.040 [+0.019, +0.062], 18 W / 8 L.
  - Judge - LTF: +0.081 [+0.045, +0.116].
  - Judge - GTRS: +0.107 [+0.069, +0.146].
  - WA-JEPA - LTF: +0.041 [+0.003, +0.079].
- **Cost:** Drive mean 0.39 s (WA-JEPA alone 0.22 s; Alpamayo v0.3 0.41 s, which used 1,268 of the 3,000 s official budget). Driver GPU peak 5,716 MiB. About 14-22% of plans are locally corrected.
- **Judge image** `alpasim-jepa/wajepa:v2-judge-6672747` (Docker `dde3c672…`, 5.64 GB): GTRS checkpoint + vocabulary in /app/assets/gtrs (sha-checked in prepare.sh), judge on by default (R=1, margin 1), NOTICE items 6-7.
  - Mac read-only smoke test OK. Closed-loop check on shards 001 and 010 is queued after upload.
- This replaces v1 as the warmup candidate if it reproduces the native judge runs (0.989 / 0.776).

## 2026-10-01 Judge image verified: `alpasim-jepa/wajepa:v2-judge-6672747` (warmup candidate)
- Closed loop as an apptainer sandbox of the docker archive:
  - shard 001 (job 13063211): 0.989, identical to the native judge run on all 100 scenes;
  - shard 010 (job 13063212): 0.776, identical on all 100.
- 222 / 134 local corrections, the same as native. Drive mean 0.41 / 0.40 s.
- **Next (Aman):** push as `teams/amanupg:nuplan-wajepa-judge-6672747`, submit **nuplan-warmup** (the 2nd of 3 in the rolling 30 days; the 1st was 2026-09-27).
  - Read back the warmup status: success and the observed throughput wall time vs the limit.

## 2026-10-02 Official nuPlan leaderboard vs our local scores: local navtest INVERTS the official ranking
- **Warmup:** v2 judge image submitted to **nuplan-warmup**: `323ebec6-1705-4104-be10-4e3ffef3f152`, QUEUED (5/5).
- **Leaderboard** (Aman pasted 2026-10-02; 80 entries, PCS re-fit):
  - Our v0.3 entry is now PCS 1284 (rank 20/80; scene 0.8265, spacing 0.234).
  - Top host (py123d-garage) 1753 (scene 0.8955).
  - Top eligible: Lucifer AI 1553 (0.879, `routebridge-scale125-20260930`), YAX_NAM 1485, RDY Mobility 1476 (best scene score 0.902 at PCS 1423).
- **Calibration** (drivers we ran locally that also have official entries):

| Driver | Local mean scene score (shards) | Official scene | Official PCS |
|---|---|---|---|
| Alpamayo v0.3 | 0.759 (001), 0.510 (010) | **0.827** | **1284** |
| go_straight_with_delay_v2 (host) | constvel stand-in 0.578 (001) | 0.799 | 1299 |
| SimScale DiffusionDrive (host) | 0.853, 0.690 | 0.772 | 1073 |
| SimScale GTRS (host/Ulsan, several configs) | 0.813, 0.730, 0.886 | 0.526-0.761 | 722-1014 |
| SimScale LTF (host) | 0.907, 0.700, 0.900 | 0.738 | 1019 |
| WA-JEPA (`wajepa-s2-20260904`, Lucifer AI, their adapter) | ours: 0.958, 0.729, 0.944 | **0.762** | **1022** |

- **Finding:** locally the NAVSIM-trained family (LTF, DD, GTRS, WA-JEPA) beats Alpamayo by a lot. Officially every one of them is below go-straight, and Alpamayo is above all of them. Public navtest flatters NAVSIM-tuned models.
  - Likely cause: they are trained/tuned on the NAVSIM benchmark the public scenes come from (the LTF checkpoint is `ltf_sim_navtest`). The private set is new to them; cf. #191.
- **Consequence:** the projected nuPlan jump from WA-JEPA is NOT supported. The one official WA-JEPA data point (another team's adapter) is PCS 1022 < our 1284. The judge's +0.04 is measured on the same flattering benchmark.
- **Clue:** Lucifer AI moved from WA-JEPA 0.762 (Sep 10) to 0.879 / 1553 (Sep 30, `routebridge-scale125`). The name suggests a route-signal fix (our known weakness: the route starts 40 m ahead, so the command is ~always STRAIGHT) and some 1.25 scaling. Contents unknown.
- **Decisions:**
  - Do not spend the official nuPlan slot on WA-JEPA as is.
  - Next: route-command fix.
  - Next: find local conditions that reproduce the official ordering of these six drivers before trusting local gains.

## 2026-10-02 nuplan-warmup SUCCEEDED (v2 judge image)
- `323ebec6-1705-4104-be10-4e3ffef3f152`, digest `sha256:dde3c672…` (= `alpasim-jepa/wajepa:v2-judge-6672747`):
  - 32/32 valid scored rollouts;
  - observed wall time **271.6 s of 2,700 s** (margin 2,428 s); started 05:47, completed 05:55 UTC.
- The form factor and real-server throughput are fine. This was the 2nd nuplan-warmup in the rolling 30 days (1st 2026-09-27); one left until ~Oct 27.

## 2026-10-02 Route command: audit and "route bridge"; trajectory time scale
- **NAVSIM's label** (NAVSIM paper/supplementary): the route-centreline point s = 20 m ahead of the ego; LEFT/RIGHT if its lateral offset exceeds +/- 2 m.
  - The organisers' sample rule reads the first route waypoint, which is ~40 m ahead (`route_start_offset_m: 40`).
- **Audit** (`src/analysis/route_audit.py`, logged route_request messages of 297 WA-JEPA rollouts on shards 001/010/005, 2,970 steps):
  - Organisers STRAIGHT: bridge agrees 1,345, says turn 29.
  - Organisers LEFT/RIGHT: bridge agrees 1,035, says **STRAIGHT 551** (19% of all steps), says the opposite turn 10.
  - **Correction:** the earlier note "the organisers' rule almost always gives STRAIGHT" was wrong. It over-signals turns relative to NAVSIM's label.
- **Route bridge** (`route_bridge.py`, `WAJEPA_COMMAND=bridge`): cubic Hermite from the ego (heading +x) to the first waypoint (route heading), then NAVSIM's s = 20 m / 2 m rule. Unit-tested on synthetic straight, gentle-curve, turned and empty routes.
- **Trajectory time scale** (`timewarp.py`, `WAJEPA_TIME_SCALE`): the organisers' GTRS-sample warp in [1.0, 1.25]. It reads the plan ahead in the near term (t <= 1 s at scale*t, then +lead tapering to 0 at 4 s) so the MPC keeps up; the endpoint is unchanged.
  - Lucifer AI's top-eligible image `routebridge-scale125` (0.879 / PCS 1553) matches **route bridge + time scale 1.25** (inference from the name, not verified).
  - Official dist_to_gt is ~2.2 m for the NAVSIM samples vs ~0.7 m for the top entries, consistent with plan-tracking lag.
- **Runs:** WA-JEPA and the judge, each with bridge and bridge + scale 1.25, on shards 001/010/005 (13101161-66, 13101187-92).

## 2026-10-02 WA-JEPA ignores the drive command; route snapping instead
- **Bridge command alone changes nothing:** WA-JEPA + bridge on shard 001 = 0.958 and judge + bridge = 0.989, identical to the organisers' rule on all 100 scenes (13101161/62). The setting reached the driver (variant.env WAJEPA_COMMAND=bridge).
- **Direct test** (CPU, real frames dumped from run 12994800, call 100, ego 10.5 m/s): the plan at 4 s is (42.16, 3.30) LEFT, (42.13, 3.32) STRAIGHT, (42.30, 3.30) RIGHT, (43.33, 3.41) UNKNOWN.
  - **WA-JEPA's plan does not depend on LEFT/STRAIGHT/RIGHT** (cm-level); it follows the visible road, so at junctions it cannot be told the branch.
  - The remaining bridge-only runs were cancelled (13101163-66).
- **Route snapping** (`snap_plan_to_route`, `WAJEPA_ROUTE_SNAP=1`): keep each plan pose's arc length (progress) and the model's own path within 5 m. Blend linearly onto the bridged route by 25 m; yaw from the blended path; no change without a route or when stationary. Unit-tested.
  - The route is a runtime input (the policy receives it every step), so this is allowed.
- **Runs:**
  - judge + snap and judge + snap + scale 1.25 on shards 001/010/005 (13101796-801);
  - WA-JEPA / judge + bridge + scale 1.25 (13101187-92; the bridge is a no-op, so these isolate the time scale).

## 2026-10-02 Leaderboard update (Aman, team view: 28 of 84 entries)
- **We are 8th of 28 teams** (PCS 1290, v0.3); 6th among non-host teams.
- **SymPhi `sp-1002a`** (submitted 2026-10-02 08:10): **PCS 1809, scene 0.94, at-fault distance 0.814, #1 overall** (above the host's 1762). Their previous entries were VaVAM-based at 0.55-0.70 scene score (`sp-0926b` 0.70).
- Lucifer AI's 1560 entry (`e61f63b5`) now displays tag `lf-007`. It showed `routebridge-scale125-20260930-ee3099b0` in the 2026-10-02 JSON, so the name-based reading is weaker.
- Go-straight alone scores 0.799 officially (most private scenes are simple), so route following + safe speed may be the main lever.
- **Diagnostic queued:** a pure route follower (constant current speed, plan snapped to the route; `WAJEPA_ABLATE=constvel` + `WAJEPA_ROUTE_SNAP=1`) on all 3 shards.

## 2026-10-02/03 Snap + time-scale results (300 scenes) and the public py123d baseline
| Config (shards 001+010+005) | Score | Offroad | Corridor | Collision | Progress | dist_to_gt |
|---|---|---|---|---|---|---|
| WA-JEPA | 0.877 | 0.077 | 0.020 | 0.007 | 0.961 | 1.24 |
| + judge (R1 m1) | 0.917 | 0.037 | 0.017 | 0.010 | 0.988 | 1.52 |
| + judge + route snap | **0.923** | 0.030 | 0.013 | 0.013 | 0.989 | 1.38 |
| route follower (no model) | 0.548 | 0.170 | 0.110 | 0.043 | 0.701 | 1.78 |
| + time scale 1.25 (any combination) | 0.60-0.67 | 0.09-0.13 | 0.06-0.08 | **0.16-0.21** | 1.09-1.10 | **6.6** |

- Paired: snap vs judge +0.006 [-0.014, +0.026] (neutral locally, fewer offroad/corridor). Time scale -0.21 to -0.33.
- **Time scale hurts WA-JEPA:** the warp pushes the car ahead of the plan, and WA-JEPA replans from the higher speed, so the speed runs away (rear-end collisions). Dropped for WA-JEPA.
- Infrastructure: several runs failed because the MTGS renderer took >30 min to start on ins038/039/058/060/061. Launcher timeout raised to 3600 s; failed runs were resubmitted.
- **Public py123d_garage checkpoint** (`kesai-labs/py123d_garage_pretrained_checkpoints` @ 5516edd, `resnet34_v0.1.0/model_0014.pth`, Apache-2.0, not gated; "the reference starting point for the Alpasim E2E Challenge 2026").
  - Official entries with this checkpoint: host `014-nuplan-0014-v1` 0.848 / 1484; **YAX_NAM `base0014-v1` 0.848 / 1487**; Lucifer AI (2026-09-24) 0.848 / 1485.
  - So the public baseline is worth about **PCS 1485**, vs our Alpamayo 1288 and WA-JEPA (Lucifer) 1022.
  - The host's 0.896 "0062" entries use a private repo (`py123d_garage_dev_pretrained_checkpoints`).
- **Conclusion for the JEPA question:** on nuPlan the official evidence favours the py123d family over WA-JEPA.
  - Proposed to Aman: (A) pivot the nuPlan slot work to the py123d base + our levers, keeping JEPA as judge/second opinion if it measurably helps; (B) keep a pure-JEPA research line; (C) both. Awaiting his decision.

## 2026-10-03 Plan C (Aman: do both)
- **Why local != official, working hypothesis:** public navtest is the NAVSIM benchmark these models were tuned/selected on. Some were trained on simulated copies of navtest (`ltf_sim_navtest`). The private set is a fresh exam.
  - Alpamayo (never tuned on navtest) goes up officially (0.759 → 0.827); the NAVSIM-tuned family goes down to below go-straight.
  - **Test:** py123d's public checkpoint was trained on nuPlan train/val (+PAI), not navtest, and scores 0.848 officially. If the hypothesis holds, its local score should not tower over the others the way LTF's does.
- **What local evaluation is good for:** comparing variants of one model (shared bias largely cancels). It is not trusted for ranking model families against each other; calibration against the 6-7 drivers with official scores decides how far it can be used.
  - Container names are hints only. The "0014" link is supported by the release notes and three identical official scores.
- **Track A (slot):** py123d_garage v0.1.1 + public resnet34_v0.1.0/model_0014.pth (route-conditioned: target point 45 m along the route; 3 cameras stitched 1024x256).
  - Set up in its own venv (setup_garage.sbatch, job 13121248; alpasim_grpc from our own archive, not the read-only checkout); DRIVER=garage in sim_nuplan.sbatch.
  - Then local runs on the 3 shards, calibration, and add-ons (GTRS judge, route snap, time scale).
- **Track B (background):** WA-JEPA frozen-encoder fine-tune pilot on simulator-rendered scenes; GPU only when track A is idle.

## 2026-10-03 py123d public checkpoint locally: the hypothesis holds (local scene score cannot rank model families)
- `DRIVER=garage` (py123d_garage v0.1.1, resnet34_v0.1.0/model_0014.pth, sensor_rig_0; jobs 13121307-09, L40S, ~20 min each, Drive 0.02 s):
  - shard 001: 0.787 (90 passed); shard 010: 0.656 (78); shard 005: 0.841 (91);
  - progress 0.75-0.83, dist_to_gt 0.62-0.93 m, at-fault collision 0.00-0.01, offroad 0.07-0.18.

| Driver | Official scene | Local 001 / 010 / 005 | Local progress | Local dist_to_gt |
|---|---|---|---|---|
| py123d 0014 | **0.848** | 0.787 / 0.656 / 0.841 | 0.75 | **0.76** |
| Alpamayo v0.3 | 0.827 | 0.759 / 0.510 / - | 0.79 | 1.65 |
| DiffusionDrive | 0.772 | 0.853 / 0.690 / - | 0.88 | 1.64 |
| WA-JEPA | 0.762 (Lucifer's adapter) | 0.958 / 0.729 / 0.944 | 0.94 | 1.27 |
| GTRS | ~0.761 | 0.813 / 0.730 / 0.886 | 1.01 | 3.67 |
| LTF | 0.738 | 0.907 / 0.700 / 0.900 | 0.89 | 1.46 |

- **The official best of this group (py123d, not navtest-tuned) is near the local bottom; the NAVSIM-tuned models top the local table.** The local scene score is not usable across model families.
  - Within-family comparisons remain the tool. Local dist_to_gt ranks py123d first in both views (weak signal only).
- py123d locally: closest to the path, slow (progress 0.75), its failures mostly offroad.
- **Add-on launcher** `src/garage_addons/entry.py`: runs py123d's own driver after wrapping `driver_service._make_plan` (no code changes). First add-on: GARAGE_TIME_SCALE (the organisers' warp).
  - Runs: 1.10 and 1.25 on the 3 shards (13122666-71).

## 2026-10-03 Shared filesystem full; cleanup (Aman approved per item)
- **2026-10-02 ~22:17 UTC:** /insomnia001 (department quota 5.0 TB) at 100%, 1.3 GB free.
  - Four py123d time-scale runs died writing output (exit 120): 13122666, 13122669, 13122670, 13122671.
  - alpasim-jepa held 296 GB, of which runs 173 GB, almost all per-scene `rollout.asl` logs (~27 MB each, ~95% embedded camera JPEGs).
- **Deleted** (approved): sandboxes wajepa-dev and wajepa-v1 (16.6 GB, superseded by the verified v2), the uploaded v2 image tar (5.3 GB), the apptainer build cache (5.3 GB). Kept the logs (Aman: auditing matters).
- **Slimmed the logs instead** (`src/analysis/slim_asl.py`, approved after a one-run test): every LogEntry kept in order; only `driver_camera_image.camera_image.image_bytes` emptied.
  - Verified per file: same entry count and kinds, non-image entries byte-identical, image entries identical apart from the bytes.
  - The route audit on slim vs original logs gives identical output (same md5).
  - Result: **5,611 logs, 183.91 GB -> 1.97 GB, 0 failed**; originals deleted after verification. runs/ now 2.7 GB; filesystem 192 GB free (97%).
  - Lost: re-rendering video / replaying exact pixels (re-run a scene if needed).
- Sims now slim their own logs after scoring (sim_nuplan/sim_pai end step).
- Insomnia folders: alpasim, alpasim-jepa, nureasoning, wearable. The `wearable` project (unknown to this thread) is actively ingesting data (jobs fm_ingest, sam3_dl, fmtrk_s21). Aman will brief the other agents.

## 2026-10-03 py123d + time scale (paired vs py123d baseline per shard)
| Scale | Shard 001 | Shard 010 | Shard 005 | W / L (all) |
|---|---|---|---|---|
| 1.10 | +0.012 [-0.012, +0.035] | -0.062 [-0.110, -0.019] (offroad 0.18 → 0.24) | +0.007 [-0.028, +0.040] | 72 / 16 |
| 1.25 | -0.118 [-0.183, -0.058] | -0.124 [-0.184, -0.067] | -0.080 [-0.144, -0.020] | 68 / 48 |

- **1.25** adds collisions and drift (dist_to_gt 4-5 m).
- **1.10** fixes py123d's slowness on many scenes (72 W) but loses badly on curves (offroad).
- **Next:** warp only near-straight plans (heading change over 4 s < 10 deg, `GARAGE_TS_MAX_TURN_DEG`), at 1.10 and 1.15 (13142131-36).
- Storage: 394 GB free (93%) after the other agents' cleanups.

## 2026-10-03 py123d + time scale only on near-straight plans (heading change < 10 deg over 4 s)
| Scale | Shard 001 | Shard 010 | Shard 005 | W / L |
|---|---|---|---|---|
| **1.10, straight only** | **+0.012 [+0.007, +0.017]** | -0.010 [-0.036, +0.011] | **+0.029 [+0.013, +0.049]** | **64 / 8** |
| 1.15, straight only | +0.007 [-0.014, +0.022] | -0.036 [-0.076, -0.000] | +0.017 [-0.015, +0.048] | 63 / 15 |

- The straight-only gate removed most of 1.10's curve losses (shard 010: -0.062 → -0.010) and kept the progress gains.
- **Current best py123d add-on: 1.10 straight-only** (~+0.01 pooled; same-model comparison, so locally meaningful).
- **Slot candidate:** py123d 0014 + this add-on (expected ~PCS 1485+, vs our 1288).
- **Options proposed to Aman for a bigger jump:**
  1. py123d fine-tune with the public recipe (the host's private fine-tune "0062" reaches 0.896 officially);
  2. GTRS judge on py123d (it cut offroad for WA-JEPA locally; NAVSIM-family risk);
  3. JEPA fine-tune pilot (background).

## 2026-10-03 October slot plan (Aman)
- **Slot 1:** nuPlan = WA-JEPA + GTRS judge (the verified v2 image, digest `sha256:dde3c672…`), to get WA-JEPA's real official number with our adapter. Tag **`v4`**.
- **Slot 2:** PAI = the main line's best (its call).
- **Slot 3:** the track with the better chance to win, decided on the official results.
  - If WA-JEPA ends < ~1485 and nuPlan gets slot 3, use py123d + straight-road speed-up (image being prepared now).
- **Tags:** neutral version labels only (`v4`, `v5`, …); the leaderboard shows tags publicly (memory: neutral-image-tags).

## 2026-10-03/04 GTRS judge on py123d (GARAGE_JUDGE=gtrs, R=1 m, margin 1, organisers' command)
- Code: `src/garage_addons/entry.py` (wraps the garage driver: caches raw L0/F0/R0 1080p frames and egomotion, judges py123d's plan with `wajepa_challenge.judge.GtrsJudge`, then the time warp runs as before). Built in the fork session, continued here.
- Smoke run 13154156, shard 001: 1000 judge calls, no errors; GTRS path used in 306 (31%).
  - **+0.031 [90% +0.002, +0.065]** vs py123d base (0.818 vs 0.787), offroad 0.08 → 0.04, collisions 0.00, progress 0.76 vs 0.75.
  - But **W8 / L15**: the gain comes from a few big offroad saves, with more small losses. Not trusted until shards 010 and 005.
- Queued: judge on 010/005 (13157459/60), judge + 1.10 straight-only on 001/010/005 (13157461-63).
- Storage note: /insomnia001 now shows 1.7 PB with 496 TB free (filesystem expanded since the cleanup).
- **All 3 shards (paired vs py123d base, 300 scenes):**

| Config | Pooled diff [90%] | W / L | Per shard 001 / 010 / 005 | Offroad | Collisions |
|---|---|---|---|---|---|
| base | | | 0.787 / 0.656 / 0.841 | 0.107 | 0.003 |
| judge | **+0.016 [-0.000, +0.033]** | 22 / 39 | +0.031 / +0.010 / +0.005 | 0.077 | 0.003 |
| judge + 1.10 straight-only | +0.014 [-0.006, +0.036] | 59 / 30 | +0.047 / -0.006 / +0.003 | 0.087 | 0.010 |
| 1.10 straight-only (earlier) | +0.010 [-0.000, +0.020] | 64 / 8 | +0.012 / -0.010 / +0.029 | 0.110 | 0.003 |

- The judge's profile: it rescues failing scenes (9 wins > 0.5, 1 loss > 0.5; nonzero-score scenes 259 → 267) and pays with many small progress losses (39 losses totalling -4.4, vs 22 wins totalling +9.0).
- Judge + warp is not additive and triples collisions; likely the warp applied to substituted GTRS paths.
- Queued (13158677-82): judge + 1.10 straight-only with no warp on judged plans (`GARAGE_TS_SKIP_JUDGED=1`, new), and judge with margin 2 (fewer, more confident swaps).
- Caveat: the judge is NAVSIM-trained (navhard). Cross-family transfer to the official score is unknown; the v4 WA-JEPA + judge official result will be the first evidence.

## 2026-10-04 Judge margin and warp-skip (paired vs py123d base, 300 scenes)
| Config | Pooled diff [90%] | W / L | Big W / L (>0.5) | Per shard 001 / 010 / 005 | Offroad | Collisions |
|---|---|---|---|---|---|---|
| judge m1 | +0.016 [-0.000, +0.033] | 22 / 39 | 9 / 1 | +0.031 / +0.010 / +0.005 | 0.077 | 0.003 |
| **judge m2** | **+0.027 [+0.011, +0.044]** | 20 / 14 | 10 / 1 | +0.037 / +0.017 / +0.028 | 0.073 | 0.003 |
| judge m1 + 1.10 straight-only | +0.014 [-0.006, +0.036] | 59 / 30 | 9 / 6 | +0.047 / -0.006 / +0.003 | 0.087 | 0.010 |
| judge m1 + 1.10 straight-only, skip judged | +0.023 [+0.004, +0.042] | 60 / 27 | 9 / 3 | +0.046 / +0.002 / +0.021 | 0.083 | 0.003 |

- Margin 2 keeps the rescues and drops most of the small losses: the best and the only one positive on every shard.
- Skipping the warp on judged plans removes the extra collisions (0.010 → 0.003).
- Queued (13159124-29): judge m2 + warp skip-judged, and judge m3.
- **Results (13159124-29):**
  - judge m3: +0.025 [+0.011, +0.040], W13 / L6, big W8 / L0, per shard +0.027 / +0.020 / +0.028.
  - **judge m2 + 1.10 straight-only skip-judged: +0.033 [+0.015, +0.052]**, W69 / L18, big W10 / L3, per shard +0.049 / +0.007 / +0.044, collisions 0.003. **Best so far.**
- m2 and m3 are a plateau (not a knife-edge setting).
- Queued (13159172-77): a rerun of the py123d base on all 3 shards (measures run-to-run noise, never measured for py123d), and m3 + warp skip-judged.
- **Results (13159172-77):**
  - judge m3 + warp skip-judged: +0.032 [+0.015, +0.049], W70 / L12, big W8 / L2, per shard +0.038 / +0.010 / +0.047.
  - **py123d base rerun: identical on all 300 scenes** (bit-for-bit scene scores, different nodes). The simulator is deterministic for this driver, so every paired difference above is caused by the add-on, not run noise. The remaining uncertainty is which scenes we sampled (the bootstrap interval) and transfer to the official score.
- About 8 settings were tried on these 300 scenes, so the best one is mildly overfit. Held-out check: fetching asset part 013 (~32 GB, public, fetch job 13159236), scenes = the new assets only. It runs base, judge m2, m2 + warp skip, m3 + warp skip, warp alone.

## 2026-10-04 Held-out check on fresh shard 013 (100 scenes, logs 2021-09-29 veh-28 and 2021-10-06 veh-52, never used for tuning)
| Config | Shard 013 diff [90%] | W / L | Offroad | Collisions |
|---|---|---|---|---|
| base | 0.686 | | 0.16 | 0.04 |
| judge m2 | +0.046 [+0.017, +0.082] | 8 / 2 | 0.12 | 0.03 |
| **judge m2 + 1.10 straight-only skip-judged** | **+0.049 [+0.011, +0.092]** | 20 / 4 | 0.13 | 0.02 |
| **judge m3 + 1.10 straight-only skip-judged** | **+0.049 [+0.011, +0.092]** | 20 / 4 | 0.13 | 0.02 |
| 1.10 straight-only | +0.004 [-0.018, +0.026] | 16 / 3 | 0.17 | 0.03 |

- **The gain holds on unseen scenes** (larger than on the tuning shards). m2 and m3 differ (169 vs 129 swaps; 98/100 scenes identical), same mean here.
- Over all 400 scenes: m2 + skip ≈ +0.037, m3 + skip ≈ +0.036.
- **Pick: judge m3 + 1.10 straight-only skip-judged.** It matches m2 with ~25% fewer swaps and fewer losses on the tuning shards (12 vs 18). Fewer interventions mean less exposure to the open question of whether the NAVSIM-trained judge transfers to the official score.
- Settings: `GARAGE_JUDGE=gtrs GARAGE_JUDGE_MARGIN=3 GARAGE_JUDGE_RADIUS=1 GARAGE_TIME_SCALE=1.10 GARAGE_TS_MAX_TURN_DEG=10 GARAGE_TS_SKIP_JUDGED=1`.

## 2026-10-07 Aman: the nuPlan entry may be our only shot
- Undecided whether nuPlan or PAI gets 2 of October's 3 slots. If nuPlan gets 1, Aman submits in the last week of October; if 2, the first around mid-October.
- **Rule from now:** keep improving; adopt a change only if it is positive on the 300 tuning scenes AND on held-out scenes never used for choosing. The simulator is deterministic, so the noise is which scenes we sampled: grow the held-out pool. Shard 013 was used once (to pick margin 3), so new held-out parts 007 and 011 are being fetched (13244453 and a follow-up).
- py123d_garage licence re-checked: GPL-3.0 was added on 2026-08-24 but replaced by Apache-2.0 at v0.1.0; v0.1.1 (ours) is Apache-2.0. No newer checkpoint or release since 2026-09-10.

### The host's 0.896 "0062" checkpoints: what they probably are
- The checkpoint README documents fine-tuning: nuPlan posttraining (`scripts/training/nuplan/latent_transfuser/posttrain.sh`) from `model_0014.pth`.
- That script's own default init is `pretrain_latent_transfuser_nuplan/.../model_0062.pth`, and the nuPlan-only preset `ltf_nuplan_trainval` has `max_epochs=63` (the public mixed checkpoint: 15).
- So the host's `nuplan-0062` entries (0.896 vs 0.848 for `nuplan-0014`) are most likely the **nuPlan-only recipe at ~4x the epochs**. This is an inference from names and configs, not a confirmed fact.
- That makes py123d training the biggest lever left, and it would stack with the add-ons. Storage no longer limits it (493 TB free). Data: `kesai-labs/nuplan`, public, not gated, nuPlan (nuScenes) non-commercial terms. Train/val only; `nuplan_test` holds navtest, which our local scenes come from, so it is never used.
- **Measuring the cost first** (small jobs): `cluster/py123d_data.sbatch` fetches 8 train + 2 val logs (3 front cameras + lidar + metadata) and builds the latent TransFuser cache, timing both (13244241). `cluster/py123d_train.sbatch` (posttrain from 0014, nuPlan preset, W&B off) will time training steps on that cache.
- Cluster: jobs landing on ins095, ins040 and ins084 failed instantly (exit 0:53 / NODE_FAIL) while the same job ran fine elsewhere; those nodes are excluded for now.

### Add-on variants queued on the tuning shards (13244455-60)
- Best (judge m3 + 1.10 straight-only skip-judged) with the judge's drive command from the route bridge instead of the organisers' rule; and with judge radius 2 m.

## 2026-10-07 Aman: keep the JEPA track alive (do not put everything on py123d)
- Upstream check: WA-JEPA code still @ bec2966 (2026-09-04), weights @ 15c0770e (2026-08-21); AD-E2E-JEPA repo still README only. Nothing new to adopt.
- **JEPA track plan:**
  1. **Now:** WA-JEPA judge margin 2 and 3 (R=1) on the tuning shards (13244639-44). Only margin 1 was ever tried at R=1, and on py123d margins 2-3 clearly beat margin 1. Held-out confirmation follows on parts 007/011.
  2. **Route conditioning (the main JEPA research item):** WA-JEPA ignores the route command, while py123d (route-conditioned, 45 m target point) scores much higher officially. Pilot: keep the JEPA encoder frozen and fine-tune the planning head with a route target-point input on nuPlan train/val in 123D format, the same data being fetched for py123d (shared download). Needs a 123D → WA-JEPA input adapter; scoped after the py123d data probe shows data cost.
  3. Official evidence: if nuPlan gets 2 slots, the WA-JEPA entry (`v4`) is the JEPA test on the real benchmark.

### WA-JEPA route-conditioning pilot: scoping (read-only study of WA-JEPA @ bec2966)
- **Where the command enters:** only via `ego_status` [8] = command one-hot (4) + vx, vy, ax, ay → `ego_status_encoder` (Linear 8→512) → broadcast to the 8 trajectory tokens → `traj_fusion`. It never reaches the scene/context streams; there is no command dropout. In stage-1 nuPlan data the command is derived from the GT future, in NAVSIM from `driving_command`. Plausible reasons it is ignored: velocity + history dominate, mostly-straight data.
- **Planner:** joint flow-matching predictor (12 blocks, width 512, ~170M) over context (4096 tokens), future scene (8192) and trajectory (8) streams, 4 Euler steps. The "head" is the trajectory stream inside the predictor.
- **Least-change design:** `ego_status_dim` 8 → 10 with the route target point (x, y); copy the old 8 input columns and zero-init the 2 new ones, so the model starts out exactly as now. (Alternative: a separate target-point encoder with a zero-init output, added as a 4th input to `traj_fusion`.) Our adapter needs `ego_status_dim` and a non-strict load (policy.py:95-105).
- **Cheap training:** with the encoder and projector frozen, `context_scene` [4096, 512] (4 MiB bf16 per sample) can be cached exactly (inference and training both mask the full future; ViT has no dropout). Train only trajectory-stream parameters (`noisy_traj_proj`, `history_traj_encoder`, `ego_status_encoder`, `traj_fusion`, `traj_out`, per-block `traj_*`): context/scene see the trajectory K/V detached, so no backward through the frozen streams. The scene stream still runs forward (needs noisy future-scene inputs: cache EMA future tokens, 8 MiB per sample, or another scheme). Custom code, not in the repo.
- **Data implication:** WA-JEPA uses 4 cameras (l0, f0, r0, **b0**) at 256x512 with 4 history frames. The py123d download excludes b0, so the full nuPlan fetch must include `camera.pcam_b0` for the JEPA pilot (shared data, one download).

## 2026-10-07 py123d add-on variants on the tuning shards (13244455-60)
| Variant of best (judge m3 + 1.10 straight-only skip-judged) | vs base | vs best, paired [90%] | W / L vs best |
|---|---|---|---|
| judge command from the route bridge | +0.029 | -0.003 [-0.012, +0.007] | 22 / 22 |
| judge radius 2 m | +0.043 (all 3 shards positive; offroad 0.087 → 0.060; collisions 1 → 2 of 300) | +0.011 [-0.007, +0.029] | 32 / 25 |
- Bridge: rejected. Radius 2: not clearly better than best (interval spans zero, one new collision). Sent to held-out 013/007/011 (bestr2 runs) before any decision.
- Held-out pool now: 013 (100 scenes, used once), 007 (61 new scenes), 011 (100 new scenes). 007/011 baselines + current bests for py123d and WA-JEPA queued (13249555-62).
- Queue: our fair share is the lowest in `edu`, so sims ran one at a time with ~6 h estimated gaps. Fixed by allowing L40 and H100 (both in the renderer's 8.9/9.0 arch list) and a 1 h 15 min limit (runs take 20-35 min), which lets the scheduler backfill. `cluster/sim_nuplan.sbatch` now defaults to this.
- `src/analysis/report.py`: every config vs its model's baseline, tuning and held-out groups separately.

## 2026-10-07 py123d training cost, measured (10 nuPlan logs)
- **Download:** 10 logs (3 front cams + lidar + metadata) 21.7 GB in 893 s, about 24 MB/s unauthenticated, one stream. Per log: cameras ~0.45 GB each, lidar 0.75 GB (35%), metadata ~0.04 GB.
- **Cache:** 390 s on 16 CPUs for 10 logs; 2.4 GB (train 1.9 GB, val 0.53 GB). Needs a separate env (`envs/garage-train`, extra "train": lightning 2.6.6, torch 2.8.0+cu128); the eval env stays unchanged.
- **Samples:** 1,777 training samples from 9 logs with scenes (1 s anchor spacing), about 200 per log, so the full train+val (~1,310 sensor logs) is roughly 230-260k samples per epoch (~3.9k steps at batch 64).
- **Speed:** one RTX A6000, batch 64, bf16, `max-autotune`: ~225 samples/s once compiled (compile ~11 min; Triton shared-memory fallbacks on A6000 are harmless). So **~20-30 min per full epoch on one A6000.**
- **Schedule:** cosine warm restarts, T_0 = 1 epoch, T_mult = 2, so cycles end at epochs 1, 3, 7, 15, 31, 63. The public checkpoint is the end of cycle 4 (15); the nuPlan recipe runs to the end of cycle 6 (63), consistent with the host's "0062".
- **Fixes:** srun refused to start after an in-place job edit (SLURM_TRES_PER_TASK vs SLURM_CPUS_PER_TASK; unset it). The run finished training but never exited (idle 1 h 45 min): `py123d_train.sbatch` now stops it after "Training finished". `STAGE=pre|post` added.
- **No-lidar check** (13256936): 2 more logs without lidar and with the rear camera (WA-JEPA needs it), then the cache, to confirm the latent TransFuser needs no lidar (saves ~1 TB).

## 2026-10-07 Held-out results (parts 013/007/011, 261 scenes) and a new py123d best
| py123d config (vs py123d base, paired) | Tuning 300 | Held-out 261 | Held-out per part 013 / 007 / 011 |
|---|---|---|---|
| judge m3 R1 + 1.10 straight-only skip-judged (previous best) | +0.032 [+0.016, +0.049] | +0.026 [+0.008, +0.045], W51 / L13 | +0.049 / +0.032 / -0.000 |
| **judge m3 R2 + same warp** | **+0.043 [+0.020, +0.066]** | **+0.058 [+0.034, +0.082], W61 / L15** | +0.087 / +0.067 / +0.023 |
- **R2 vs R1 paired:** tuning +0.011 [-0.007, +0.029]; held-out **+0.032 [+0.011, +0.053]**, 11 big wins / 1 big loss, no new collisions. **Adopted: R2 is the new py123d recipe.** Held-out collisions 0.019 vs base 0.027.
- Parts 013/007/011 have now been used to choose R2. Further choices need fresh scenes: parts 003 and 014 are being fetched (13258237-38, `cluster/fetch_heldout.sbatch`).
- Queued on tuning: R3 (13258225-27).

| WA-JEPA judge (R1) vs WA-JEPA base | Tuning 300 | Held-out |
|---|---|---|
| m1 (the v4 image) | +0.040 [+0.020, +0.063], W18 / L8 | +0.029 [+0.008, +0.053] on 007/011 (161), W6 / L6 |
| m2 | +0.043 [+0.023, +0.064], W22 / L5 | queued (013/007/011) |
| m3 | +0.022 [+0.002, +0.044] | rejected |
- The WA-JEPA judge holds on held-out scenes. m2 vs m1 is within noise on tuning; held-out decides (13258228-32 incl. the WA-JEPA 013 baseline).
- Queue fix confirmed: all 23 sims of the evening ran within ~3 h.

## 2026-10-07 Training pipeline queued (Aman approved the full plan: download, cache, py123d A + B, WA-JEPA pilot)
- **nuPlan 123D download** (13256952, 12 tasks): all 1,310 train + val sensor logs, cameras l0/f0/r0/b0, no lidar; ~80 MB/s total, ~9 h. The latent TransFuser needs no lidar (no-lidar logs passed py123d's filter and cached).
- **WA-JEPA route pilot, verified** (`src/wajepa_route/verify.py`, 6 samples): cached-feature inference matches `predict_trajectory` exactly (max diff 0.0000 m); the zero-init target-point encoder changes nothing (0.000000); trainable = 58.6M of 788M (trajectory stream + target-point encoder); gradients reach only those. Sample builder checked visually (camera order l0, f0, r0, b0; RGB).
- **Chained:** py123d cache (13256971, 16 shards) → fine-tune A (13260084 + resume 13260085: from public 0014, nuPlan only, 15 epochs, 1 A6000, keeps epochs 3/7/15). WA-JEPA feature cache (val 13260076, train 13260077; anchors every 4 s, ~12.6 MB/sample) → pilot runs **route** (13260079) and **control without the route input** (13260080), so the route effect is separated from the effect of fine-tuning alone.
- Recipe B (py123d from scratch, 63 + 63 epochs, multi-GPU) waits for the 2-GPU probe (13256973).

## 2026-10-07/08 INCIDENT: dept storage filled to 100% by the nuPlan download
- **Cause (my error):** the 5 TB edu fileset quota was read from `df -h /insomnia001`, which shows the whole 1.7 PB filesystem ("490 TB free"). The fork session had concluded "the filesystem was expanded" from the same reading, and I relied on it without checking the quota. The 123D download (12 tasks) wrote ~197 GB before hitting "Disk quota exceeded"; free space dropped to 768 MB, so every writer on the fileset (including the other threads' jobs) could fail.
- **Response:** cancelled all my jobs (download array, cache, training chains, held-out fetches, queued sims); inventoried today's data; Aman approved deleting `data/py123d/nuplan/123D/logs` (197 GB, partial public download) and its `.cache` (0.9 GB). Free space back to **199 GB (97%)**.
- **Rule recorded** (memory: cluster-etiquette): measure the quota with `df -h /insomnia001/depts/edu/users/au2327`; keep >= 200 GB free before any download.
- **Consequence for the plan:** full-dataset training (2.5 TB raw + ~330 GB py123d cache + WA-JEPA features) does not fit the fileset. Needs a storage decision from Aman (see below).
- Kept: `data/nuplan_track` (173 GB, all local eval scenes), py123d cache of the 12 test logs (2.7 GB), maps + index.
- **Aman (2026-10-08): option 2, node-local disk only; the other threads keep their data.** GPU nodes have a 200 GB `/local` (job `$TMPDIR`, wiped at job end; `TmpDisk=0`, so it cannot be reserved and up to 8 jobs share it): each job downloads batches of logs to `/local`, builds its cache/features there, deletes the raw batch, trains, and writes only logs and small checkpoints to the fileset.
  - py123d: `cluster/py123d_local_probe.sbatch` (13278997) tests the key assumption that training works from the cache after the camera files are deleted (scene listing reads only metadata).
  - WA-JEPA pilot: `cluster/wajepa_route_local.sbatch` (batches of 12 logs, features capped at 100 GB ≈ 8k samples, peak local use ~150 GB; route run then the no-route control on the same features). Small end-to-end run first (13279184: 24 train + 4 val logs, 1 epoch).
- **py123d node-local result (13278997):** after deleting the camera files, training still listed every scene (814 samples from 4 logs) from the metadata + cache. So a job only keeps the compact cache (~0.25 GB/log) on /local. The run then failed with "CUDA unknown error" on **ins082**; the earlier 2-GPU probe (exit 127) and the first WA-JEPA local run also died there, so ins082 is excluded too.
- `cluster/py123d_local_train.sbatch`: batches of 15 logs downloaded to a staging dir (moved in only when complete, because the cache builder scans every log dir), cached, camera files deleted; next batch prefetched; stops early if /local runs low; then trains. ~430 logs (a third of train+val, spread over the index) per job. Smoke test 13281003 (30 logs, 1 epoch) → fine-tune A 13281004 (430 logs, 15 epochs from public 0014, keeps epochs 3/7/15).
- WA-JEPA local pilot rerun with error logging (13280841; the first try left no error message).

## 2026-10-08 Radius 3 (py123d), margin 2 (WA-JEPA), fresh held-out on node-local disk
- **WA-JEPA judge m2 vs m1:** tuning +0.004 [-0.010, +0.019]; held-out (013/007/011, 261) -0.003 [-0.019, +0.014]. No difference: **keep m1 (the `v4` image as built).** The judge's held-out gain over plain WA-JEPA: +0.025 [+0.006, +0.047] (m1).
- **py123d R3** (m3 + warp skip-judged): tuning **+0.061** [+0.035, +0.088] vs base (R2: +0.043); R3 − R2 paired **+0.018 [+0.001, +0.036]**, but W33 / L44 (8 big wins / 2 big losses): fewer, larger rescues, more small losses. Not adopted until fresh scenes confirm.
- Parts 013/007/011 were already used to choose R2, and new shared parts cost ~35 GB each (no room). **New `LOCAL_PART` option** in `sim_nuplan.sbatch`: the job builds a track root on the node's /local (shared trajdata cache + configs copied, asset part downloaded) and drives only scenes of that part that are in none of our shared track copies. Fresh parts 003 and 014: base, R2, R3 (13284179-84).
- Node-local training jobs are queued but waiting: the cluster is CPU-saturated (A6000 nodes have 2-12 free cores, and our jobs need 16) and our fair share is the lowest in `edu`.
- 2026-10-09 fixes: fresh-part sims needed (1) a resumable download (a piped curl stream of the 33 GB part was cut off), (2) the node-local root bound into the wizard container, (3) a 2 h limit (download ~30 min + sim). Part 003 gives 93 fresh scenes, part 014 gives 100. R2 runs and R3 on 014 are done; base on 003/014 and R3 on 003 rerun (13286359-61).
- Node-local training jobs ran for the first time and failed on script bugs, now fixed: WA-JEPA exited silently (`set -e` + `pipefail` on a `test && echo` loop inside `$(...)`); py123d's first batch had no val log (the preset has train and val sources). Rerun: WA-JEPA small run 13286696, py123d smoke 13286697 → fine-tune A 13286698.

## 2026-10-09 Fresh parts 003 + 014 (193 never-used scenes, node-local): radius 3 adopted
| py123d, paired | Part 003 (93) | Part 014 (100) | Fresh pooled (193) |
|---|---|---|---|
| R2 recipe − base | +0.040 [+0.017, +0.067] | +0.107 [+0.059, +0.156] | +0.075 [+0.048, +0.105], W38 / L9 |
| **R3 recipe − base** | +0.044 [+0.018, +0.075] | **+0.178** [+0.120, +0.237] | **+0.113 [+0.080, +0.149], W50 / L11** |
| R3 − R2 | +0.004 [-0.016, +0.028] | +0.071 [+0.029, +0.117], 9 big W / 0 big L | **+0.039 [+0.014, +0.065]** |
- With tuning R3 − R2 +0.018 [+0.001, +0.036], R3 is positive on both sets and never worse: **adopted. py123d recipe = judge m3 R3 + 1.10 straight-only warp skipped on judged plans.** Collisions 0.00-0.01 (base 0.01-0.02); offroad on 014 0.30 → 0.07.
- Part 014 is hard for plain py123d (0.632), and that is where the judge helps most (offroad).
- **py123d node-local pipeline works end to end** (smoke 13286697: 30 logs cached in 30 min, 13 GB = 0.43 GB/log, one epoch of 10.9k samples). The job was marked failed only by its ending (watchdog kill of the post-training hang, then `ls | head` under pipefail), which blocked the chained fine-tune A. Fixed; **fine-tune A submitted: 13287171** (430 logs requested; local-disk check stops the data stage early on nodes with ~200 GB).
- WA-JEPA pilot small run 13287111 (the training module had not been synced before; all module hashes now match).

## 2026-10-09 Radius 5 / unlimited (tuning), pilot pipeline, driver integration
- **Radius vs R3** (tuning, paired): R5 +0.010 [-0.009, +0.030] (n.s.); unlimited +0.037 [+0.002, +0.072] but 26 big wins / **17 big losses**. GTRS path used in 11% (R1) / 19% (R2) / 23% (R3) / 25% (R5) / 27% (unlimited) of decisions. **R3 kept:** R5 is no better, and unlimited hands larger, unconstrained maneuvers to GTRS (a NAVSIM-family planner: ~0.761 officially vs py123d 0.848), exactly where local and official scores may disagree.
- **WA-JEPA route pilot, small end-to-end run (13287111):** data stage, route and control training and evaluation all run (4 val logs, 133 samples: too small for any signal). Training runs at 13 samples/s, so local disk for features (12.6 MB/sample) is the limit, not GPU time. **Full pilot submitted: 13287532** (up to 600 train + 20 val logs; features up to 300 GB or until /local runs low; 3 epochs; route then control).
- **Driver integration:** `WAJEPA_ROUTE_CKPT` loads the pilot's trajectory tensors (+ target-point encoder) over the released weights; the driver passes `target_point_py123d(route)`, which reproduces py123d_garage's AlpaSim target point **exactly** (0.0 m difference on 205 random routes, `src/analysis/test_target_point.py`). Training targets use py123d's `get_target_points` on the log route, so the policy gets the same signal in simulation.
- **2026-10-09 06:52 both training jobs started** on R6000 nodes (ins046/047, Blackwell; torch 2.8 cu128 supports them), after allowing `A6000|R6000`. These nodes have **14 TB of /local**, so disk does not limit jobs placed there. Rates: py123d caching ~8 min per 15-log batch (29 batches); WA-JEPA encoding ~6 min per 12-log batch. The 12 h jobs' scheduler estimates (Oct 12-13) were stale: `sbatch --test-only` showed same-day starts.

## 2026-10-09 py123d fine-tune A trained (13287171, R6000 node ins046)
- Data: 430 logs (362 train + 68 val, spread over the index), cached on /local in 5.3 h (133 GB cache); camera files deleted after caching.
- Training: from public `model_0014.pth`, nuPlan-only preset, 15 epochs (cosine restarts 1+2+4+8), batch 64, `max-autotune`, ~108k samples/epoch (1,693 steps), **~485 samples/s on one RTX PRO 6000 (Blackwell)**, ~4 min/epoch; 25,395 steps in 1 h 8 min.
- Checkpoints kept in `runs/py123d_local_ftA_13287171`: epochs 3, 7, 15 (`model_0002/0006/0014.pth`, the ends of cycles 2-4) + config + sensor rigs.
- The job showed FAILED only because the watchdog's `kill` hit an already-exited process under `set -e`; fixed (`|| true`).
- Closed-loop eval (plain, no add-ons, vs public 0014 on the same scenes): epochs 15 and 7 on the tuning shards (13295944-49).
- Implication: on R6000 nodes full-data training is cheap (~4 min/epoch for 430 logs). Data prep (~45 s/log on 16 CPUs) is the cost; the 63 + 63 epoch recipe B (~8-9 h of training on 430 logs) fits a 12 h job only without data prep, so it needs the cache to persist (14 TB /local nodes do not keep data across jobs).
- **Fine-tune A, closed loop (tuning, plain, vs public 0014 on the same scenes):** epoch 15 **+0.059 [+0.034, +0.084]**, W72 / L34, per shard 001 / 010 / 005: +0.054 / +0.063 / +0.062; epoch 7 +0.051 [+0.026, +0.076]. Offroad 0.107 → 0.040. No leakage: training used nuPlan train/val; the eval scenes are navtest (nuPlan test).
  - The first eval runs failed: the run's exported `sensor_rig_0.yaml` has no cameras (camera files were deleted after caching). `GARAGE_RIG` now passes the public nuPlan rig; **a submission image of a fine-tuned checkpoint must ship the public rig.**
  - Queued (13298612-27): fine-tune A + R3 recipe on tuning; fine-tune A plain and + R3 on held-out 013/007/011 and fresh 003/014; and the public 0014 + R3 recipe on held-out (missing so far).

## 2026-10-09/10 Fine-tune A everywhere; a GPU fault; the pilot hung
| py123d vs public 0014 base, paired | Tuning 300 | Held-out 261 | Fresh 193 |
|---|---|---|---|
| public + R3 recipe | +0.061 [+0.035, +0.088] | +0.063 [+0.032, +0.093] | +0.113 [+0.080, +0.148] |
| fine-tune A (epoch 15), plain | +0.059 [+0.034, +0.084] | +0.047 [+0.021, +0.075] | +0.036 [+0.014, +0.059] |
| fine-tune A + R3 recipe | **+0.073 [+0.046, +0.101]** | **+0.079 [+0.044, +0.114]** | (part 014 invalid, rerun 13303388) |
- **Fine-tune A alone is a consistent gain on all three sets** (+0.036 to +0.059). With the recipe it is the best on tuning and held-out.
- **Part 014 of fine-tune A + R3 was corrupted by hardware:** 26 of 100 rollouts failed with "CUDA error: uncorrectable ECC error" on **ins058** (scored 0 by the evaluator). Rerun on another node; ins058 excluded. A scan of every run found no other infrastructure failures in current results (route "folds back" scene issues and one RPC error in part 007 are identical across all drivers; the disk-quota run of the incident was already superseded). `report.py` now warns on any run with > 2 such failures.
- **WA-JEPA full pilot (13287532) timed out without training:** data ran normally for 5.4 h (31 batches, 201 GB of features), then encoding batch 32 hung after loading the model (no output for 6.6 h; most likely a stalled data-loader worker). Fixed: DataLoader `timeout=300`, fetch and encode limited per batch (30 / 40 min) and skipped on failure, a data deadline (`DATA_HOURS`, default 6 h) so training always runs. Resubmitted: 13303410 (≤ 200 GB / 6 h of data, then route and control).
- **Rerun of fine-tune A + R3 on part 014 (13303388, clean):** fresh 003+014 **+0.114 [+0.080, +0.152]** vs public base (public + R3: +0.113).
- **Fine-tune A + R3 vs public + R3, paired:** tuning +0.012 [-0.005, +0.030], held-out +0.016 [-0.011, +0.044], fresh +0.001 [-0.022, +0.025]; **all 754 scenes +0.011 [-0.002, +0.025]**, W116 / L95, big W20 / L20, P(> 0) = 0.91. The fine-tune's gain mostly overlaps with the recipe's (both cut offroad).
- **Lead candidate: fine-tune A + R3 recipe.** Reason: the fine-tune alone is positive on every set (+0.036 to +0.059) and does not depend on the NAVSIM-trained judge transferring to the official score; if the judge transfers, the combination is at least as good as the recipe alone; if it does not, the fine-tune still carries a gain. A submission image needs the public nuPlan rig (see above).
- **Fine-tune A2 submitted (13304532):** continues from A's epoch 15 on a disjoint third of nuPlan (`OFFSET=1`, 430 logs), 15 epochs.

## 2026-10-10 WA-JEPA route pilot, round 1 result (13303410): fine-tuning hurts; the route signal helps a little
- Data: 18 batches in 6 h (~9.8k train samples, 154 shards; 1,091 val samples from 20 val logs). Training ~11 samples/s on an A6000, 1,726 steps (3 epochs), lr 1e-4.

| Val (1,091 samples; 160 turns) | ADE | FDE | lat. err 4 s | Turns ADE / FDE / lat. 4 s |
|---|---|---|---|---|
| released WA-JEPA | **0.654** | **1.831** | **0.323** | **0.488 / 1.203 / 0.757** |
| route fine-tune (trajectory stream + target point) | 0.676 | 1.890 | 0.326 | 0.577 / 1.432 / 0.842 |
| control fine-tune (no route input) | 0.682 | 1.910 | 0.331 | 0.589 / 1.484 / 0.863 |
- **Fine-tuning the trajectory stream degrades the released model** (final train loss 3.3e-5: overfitting ~10k samples at lr 1e-4; the released model already trained on NAVSIM navtrain, which is built from these nuPlan train logs).
- **The route input helps relative to the control** (turns FDE 1.43 vs 1.48, lateral 0.84 vs 0.86) but not enough to offset the drift. No closed-loop test for these checkpoints (worse open-loop than the released model).
- **Round 2 (13310920), same data recipe, three runs on the same features:** target-point encoder only (lr 1e-4; the released weights cannot drift, so the route signal is the only change), route + trajectory stream at lr 1e-5, control at lr 1e-5.
- **2026-10-10 downloads throttled.** Anonymous Hugging Face downloads fell to ~1 MB/s (a 450 MB file took 8+ min) on several nodes; fine-tune A2 (13304532) could not finish its data and was cancelled after 5 h. **Aman approved** using the AlpaSim HF account's token file in place (`HF_TOKEN_PATH`, path only; account amanupg-columbia). Token + `HF_XET_HIGH_PERFORMANCE=1`: one log (1.6 GB) in 128 s (~12.5 MB/s). py123d jobs now fetch each batch as 3 parallel downloads and stop data after `DATA_HOURS` (7). A2 resubmitted with 300 logs: 13320641. WA-JEPA round 2 (13310920) started before the change (anonymous) and caps its data at 6 h.

## 2026-10-11 WA-JEPA route pilot, round 2 (13310920): negative; fine-tuning paused
- Data (anonymous downloads, throttled): 9 batches in 6 h, ~4.9k train samples (77 shards), same 1,091 val samples. 878 steps (3 epochs) per run.

| Val (1,091; 160 turns) | ADE | FDE | lat. 4 s | Turns ADE / FDE / lat. 4 s | Final train loss |
|---|---|---|---|---|---|
| released WA-JEPA | **0.681** | **1.892** | **0.328** | **0.503 / 1.215 / 0.768** | (9.2e-5 at start) |
| target-point encoder only, lr 1e-4 | 0.699 | 1.976 | 0.375 | 0.574 / 1.394 / 0.865 | 8.2e-5 |
| route + trajectory stream, lr 1e-5 | 0.697 | 1.919 | 0.331 | 0.538 / 1.308 / 0.795 | 5.9e-5 |
| control (no route), lr 1e-5 | 0.691 | 1.909 | 0.330 | 0.535 / 1.303 / 0.795 | 5.9e-5 |
- **The route input does not lower the training loss** (route = control, 5.9e-5), and the encoder-only run barely moves it, yet all runs get worse on validation. Fine-tuning lowers the training loss but raises the validation error: overfitting.
- **Reading:** the released WA-JEPA is already near its floor on nuPlan (it was trained on NAVSIM navtrain, built from these logs), and the 45 m route point adds no information beyond its cameras, history and drive command for this loss. Two rounds and six runs found no configuration that beats the released weights open-loop, so no closed-loop test is warranted.
- **Decision: WA-JEPA fine-tuning is paused.** The JEPA line stays alive as the `v4` image (WA-JEPA + judge, margin 1; judge gain +0.025 on held-out scenes) and as research; resume only with a new idea (e.g. route-aware data where the route actually disambiguates, such as intersections, or a closed-loop objective).
- Round 1 vs round 2 released numbers differ (0.654 vs 0.681) because the val sample sets differ slightly (different batches finished); comparisons are within a round.
- **Fine-tune A2 trained (13320641, A6000 node ins094):** from fine-tune A's epoch 15, on a disjoint third of nuPlan (`OFFSET=1`; 271 train + 29 val logs fetched with the token in 5.3 h), 15 epochs, 72.8k samples/epoch, 17,055 steps. Kept epochs 7 and 15. Closed-loop eval queued (13324310-25): A2 plain and A2 + R3 on tuning / held-out / fresh, compared paired against A and A + R3.
- **Candidate Q recipe written (not built):** `container/Dockerfile.q` + `NOTICE.q`: py123d v0.1.1 + our fine-tuned checkpoint (stage as `container/assets/py123d/q/{model.pth, config.yaml from the run, PUBLIC sensor_rig_0.yaml}`) + the judge (m3, R3) + 1.10 straight-only warp skipped on judged plans, GTRS code and assets, an import check and sha256 listing at build time. Which checkpoint (A or A2) is decided by the A2 evaluation; build and verify a few days before Aman's submission date (memory: nuplan-single-shot). Both candidates will be ready: WA-JEPA `v4` (built) and Q.
- Early A2 eval (5 of 16 runs, tuning only): A2 plain − A plain +0.009 [-0.004, +0.023], W54 / L26; A2 + R3 − A + R3 on 2 shards -0.007 [-0.025, +0.009]. Remaining runs queued behind a busy cluster.
- **Fine-tune A2 vs A (paired, same scenes):**

| | Tuning (300) | Held-out (261) |
|---|---|---|
| A2 plain − A plain | +0.009 [-0.004, +0.023], W54 / L26 | +0.014 [-0.002, +0.032], W36 / L30 |
| A2 + R3 − A + R3 | -0.003 [-0.016, +0.009] | -0.015 [-0.034, +0.003] |
| A2 + R3 − public + R3 | +0.009 [-0.011, +0.030] | +0.002 [-0.029, +0.031] |
  - A2 alone (vs public base): tuning +0.068, held-out +0.062 (A: +0.059, +0.047). More data helps the plain model a little; with the recipe on top, A2 is not better than A.
  - The 4 fresh-part runs failed at download: the token edit had put an inline comment in the middle of the line-continued `hf download` command, cutting off its arguments. Fixed (comment on its own line; scanned every job script for the pattern; none left) and rerun (13326362-65).
- **A2 over all 561 tuning + held-out scenes:** A2 plain − A plain **+0.011 [+0.001, +0.023]** (W90 / L56); A2 + R3 − A + R3 **-0.009 [-0.020, +0.002]**; A2 + R3 − public + R3 +0.006 [-0.012, +0.023]. More data helps the plain model slightly; with the recipe, A stays ahead.
- **Decision: candidate Q = fine-tune A (epoch 15) + R3 recipe** (fresh 003+014: +0.114 vs public base; all 754 scenes +0.011 vs public + R3). The A2 fresh-part runs (13326362-65) were cancelled: the part download from OpenDriveLab ran 1.6 h without finishing even with the token, and the result could no longer change the choice.
- **Model soup (A + A2 weights averaged, 666 float tensors; integer counters from A):** tuning plain +0.066 vs public (soup − A +0.006 [-0.004, +0.017]; soup − A2 -0.002); with R3 +0.075 (soup + R3 − A + R3 **+0.001 [-0.011, +0.014]**). No gain: **rejected.** Model variants (A, A2, soup) now differ by ~±0.01; candidate Q stays A + R3.

## 2026-10-11 Candidate Q image built
- `local/q:1` (Mac Docker, `container/Dockerfile.q`, git 8691-checkpoint): 12.8 GB (< 16 GiB). Build-time checks: `addons ok`; sha256 inside the image: model.pth `8691cc01…` (fine-tune A epoch 15), config.yaml `a0b17835…`, sensor_rig.yaml `453ddf94…` (public nuPlan rig), GTRS ckpt `8dad0395…`, vocab `e8c29cfc…` (all equal to the tested files). Docker Desktop's BuildKit timed out resolving the CUDA base image's metadata; a direct `docker pull` first fixed it.
- Exported (`docker save | gzip`, 12.8 GB, sha256 `7cc00c92…`), uploaded to Insomnia in 3.3 h (hash verified). **Apptainer could not read it** ("gzip: invalid header"; Docker Desktop's containerd export format). Shared storage then fell to **79 GB free (99%)**, mostly from other threads, so the 13 GB sandbox is not built on the fileset: a node-local test job (13334933) decompresses and converts on `/local` (docker-archive, then oci-archive). If it works, the closed-loop check (image must reproduce fine-tune A + R3 on the tuning shards bit for bit) runs entirely on `/local`, and the archive on the fileset is deleted afterwards.
- **Candidate Q verified in closed loop (13334978-80):** the image's sandbox was built on each node's `/local` from the archive (`IMAGE_ARCHIVE`, decompressed first; Apptainer cannot read Docker Desktop's gzipped export), checkpoint hashes inside equal to the tested files, add-ons active (`time scale 1.1 (only below 10.0 deg, skip judged True), judge 'gtrs'`). Against fine-tune A + R3 on the tuning shards: **001 100/100 and 010 100/100 scenes identical** (same GPU type, L40S); 005 85/100 identical, same mean to 4 decimals (H100 vs L40S floating point: 15 tiny differences, max 0.027). **Q reproduces the tested configuration.**
- The 12.8 GB archive on the fileset was deleted after the check; `local/q:1` stays on the Mac (image id `ae4b8656b624`). Fileset at **69 GB free (99%)** from other threads' growth (79 GB → 69 GB while ours went down by 12.8 GB).
- **Both nuPlan candidates are ready:** WA-JEPA + judge (`v4` in the register, image `alpasim-jepa/wajepa:v2-judge-6672747`, warmup succeeded on 2026-10-03) and **Q** (proposed tag **`v6`**; `v5` is PAI's). Push and submit only on Aman's go, after checking the tag is unused (the challenge rejects reused tags).

## 2026-10-12 Qwen-Drive-1.0 (Aman shared a post): checked, not pursued for nuPlan
- Qwen3.5-4B + BEV perception head + flow-matching Planning Expert (~1.1B), Apache-2.0 weights (HF Qwen/Qwen-Drive-1.0-4B; arXiv 2609.00111). Planning data: PAI-AV 1.38M, OpenScene ~890K, WOD-E2E 557K, NAVSIM navtrain 15K. Inputs: F0/L0/R0 x 4 frames at 0.5 s, 10 Hz ego history, ego status, nav command; output 5 s at 10 Hz. `planner-rl` must run in reasoning mode (text generation first); NAVSIM 90.7 PDMS (RL).
- **Model card, AlpaSim closed loop (at-fault score, higher is better): Alpamayo-1.5 0.45, SimWAM-IL 0.30, Qwen-Drive SFT 0.27, RL 0.37** (verified from the raw README). Alpamayo already scores below the py123d family on the nuPlan track officially (0.827 vs 0.848), so Qwen-Drive is very unlikely to beat candidate Q; a nuPlan adapter (~1 day) is not worth it now. Told the PAI agent (alpasim-alpamayo-pai), which also deprioritized it for PAI (it reports chooser v2 + route snap +0.053 over 120 PAI scenes).

## 2026-10-12 Where candidate Q still loses score (754 scenes) and the stall rescue
- Q (fine-tune A + R3) mean 0.809. **Loss from passed-but-low-progress scenes 0.100** (126 scenes with 0 < score < 0.9, mean 0.40; progress quartiles 0.03 / 0.31 / 0.54; the human drove only 10-20 m, typically from rest or crawling) **> loss from zero-score failures 0.089** (67: offroad 34, corridor 13, collision 11, scene-data route issues 8, infra 1). On those 126 scenes: plain public 0.299, public + R3 0.443, Q 0.399.
- Reading: py123d stays (nearly) stopped where the human moved off, and the radius-limited judge cannot replace a stationary plan with a moving one.
- **Stall rescue (judge.py, opt-in, off by default; the built images are unaffected):** if the chosen 4 s trajectory ends < `stall_m` from the ego, use the best GTRS vocabulary path that moves >= 3 m with collision-free and drivable-area probabilities > 0.9, when its score beats the plan's by `stall_margin`. The scene score penalizes collisions, offroad, corridor and progress (not traffic lights), so moving off is rewarded unless it causes one of those.
- Queued on tuning (13357365-70): Q + stall rescue at 1 m with margin 1 and margin 3.

## 2026-10-12 Storage cleanup in alpasim-jepa (Aman approved per item; other folders not touched)
- Inventory: 219 GB total; data/nuplan_track 173 GB (eval assets), runs 26 GB, cache/uv 9 GB, sandbox/wajepa-v2 8.6 GB, envs + weights 11 GB.
- **Deleted (approved):** 41 dead run folders (cancelled / timed out / failed; each has a completed rerun used in the results), the timing-test checkpoints (py123d_train_probe_13249480, py123d_local_smoke_13286697), the rejected soup (py123d_soup_A_A2), and the 12-log py123d cache (data/py123d/nuplan/py123d_garage_cache; index and maps kept). Kept: fine-tune A (candidate Q's checkpoint) and A2. Fileset free 64 → 80 GB.
- **Not deleted (offered, declined for now):** sandbox/wajepa-v2 (8.6 GB) and the held-out assets of parts 013/007/011 (~95 GB).
- **Stall rescue, tuning (vs Q, paired; 13357365-70):** stall 1 m, margin 1: **+0.024 [+0.009, +0.041]**, W12 / L4, big W10 / L1, new zero-score failures: 1 offroad, 1 collision; 103 of 2,970 decisions stalled, 28 rescued. Margin 3: +0.018 [+0.005, +0.033], W9 / L3, big W8 / L1, 1 new collision; 21 rescued. Held-out 013/007/011 queued (13376663-68), two lanes of serial jobs because the fileset is at 100% (49 GB free) and each sim writes ~3 GB transiently.
- **Stall rescue, held-out 013/007/011 (vs Q, paired; 13376663-68):** stall 1 m, margin 1: **+0.031 [+0.017, +0.048]**, n=261, W13 / L0, big W9 / L0, no new zero-score failures; 99 of 2,530 decisions stalled, 26 rescued. Margin 3: +0.026 [+0.013, +0.042], W11 / L0. Tuning + held-out, margin 1: +0.028 [+0.016, +0.039], n=561, W25 / L4. Fresh 003/014 (margin 1) running (13380847-48).
- **Stall rescue, fresh 003/014 (vs Q, paired; 13380847-48):** stall 1 m, margin 1: **+0.035 [+0.017, +0.054]**, n=193, W10 / L0, big W7 / L0, no new zero-score failures. **All 754 scenes (tuning + held-out + fresh): +0.030 [+0.020, +0.039], W35 / L4**, new zero-score failures only on tuning (1 offroad, 1 collision). **Adopted into candidate Q** (positive on tuning, held-out and fresh).
- **Q with the stall rescue (`local/q:2`, image id `3f315f660f72`, git 7bdfd99):** `container/Dockerfile.q` adds `GARAGE_JUDGE_STALL_M=1 GARAGE_JUDGE_STALL_MARGIN=1` (min prob 0.9, min move 3 m, the tested defaults). Build checks: `addons ok`; checkpoint, rig and GTRS hashes identical to `q:1`; judge.py / entry.py / route_bridge.py / timewarp.py inside the image equal to the files the tested runs used (sha256). Closed-loop verification (tuning 001/010 on L40S vs the `qstall1m1` runs) under way.
- **Where Q + stall rescue still loses (754 scenes, mean 0.839):** zero-score 0.092 (offroad 35, corridor 13, collision 12, route sanity-check failures 8, 1 scene-load error), partial progress 0.070 (137 scenes). Off-road guard idea rejected on the logs: decisions the judge rated low on drivable area (DAC < 0.5, not substituted, GTRS pick > 0.9) occur in 35 passing scenes vs 7 failing ones, so a guard would mostly change passing scenes. Next: widen the stall threshold (2 m, 3 m; margin 1) for crawling starts, tuning vs `qstall1m1` (13387331-36).
- **Stall threshold sweep, tuning (vs `qstall1m1`, paired; 13387331-36):** 2 m: +0.006 [-0.000, +0.014], W4 / L1 (36 rescues); **3 m: +0.013 [+0.005, +0.022], W12 / L1, no new zero-score failures** (58 rescues of 158 stalls). 3 m queued on held-out 013/007/011 and fresh 003/014.
- **`local/q:2` verified in closed loop (13388911-12):** sandbox built on node-local disk from the archive (sha256 `a0d6c44d…`, equal on Mac and Insomnia); checkpoint hashes inside equal to the tested files; vs the tested `qstall1m1` runs on the same GPU types (001 L40S, 010 L40): **001 100/100 and 010 100/100 scenes identical** (means 0.8904, 0.7606), 21 stall rescues logged. Archive deleted from the fileset afterwards. **Q (planned tag `v6`) = `local/q:2`** unless the 3 m stall threshold confirms.
- **Stall 3 m, held-out 013/007/011 (vs `qstall1m1`, paired; 13389092/93/95):** **+0.013 [+0.002, +0.025]**, n=261, W12 / L1, big W3 / L1, 1 new offroad. Fresh 003/014 runs timed out in the input stage (Hugging Face part download / extraction slow; nothing driven); resubmitted with 3 h (13391135-36).
- **Stall 3 m, fresh 003/014 (vs `qstall1m1`; 13391135-36):** **+0.012 [+0.005, +0.022]**, n=193, W7 / L0, no new zero-score failures. **All 754 scenes: 3 m − 1 m +0.013 [+0.008, +0.019], W31 / L2**, 1 new offroad (held-out). **Adopted: Q's stall threshold 3 m** (positive on tuning, held-out and fresh). `container/Dockerfile.q` now sets `GARAGE_JUDGE_STALL_M=3`; image `local/q:3` to build and verify.
- Stall 5 m queued on tuning (vs `qstall3m1`; 13396070-72) to see whether the trend (1 m → 2 m +0.006, → 3 m +0.013) continues.
- **Stall 5 m, tuning (vs `qstall3m1`; 13396070-72):** **+0.023 [+0.013, +0.034]**, W19 / L1, big W5 / L0, no new zero-score failures (108 rescues of 240 stalls vs 58 of 158 at 3 m). Trend continues: queued 5 m on held-out 013/007/011 + fresh 003/014 (13396953-57) and 8 m on tuning (13396958-60).
- `local/q:3` (3 m; image id `0d13aceb9285`, 12.79 GB per `docker image inspect`; `docker images` now shows 36GB for q:2 and q:3 alike, a display artefact) uploaded (sha256 `7c48ac7b…`, equal on both ends); closed-loop check on L40 queued (13396914-15).
- **`local/q:3` verified in closed loop (13396914-15, L40 as the tested runs):** checkpoint hashes inside equal; vs `qstall3m1`: **001 100/100 and 010 100/100 scenes identical** (means 0.9024, 0.7813); 42 stall rescues logged. Archive deleted. **Q (planned tag `v6`) = `local/q:3`**, unless 5 m confirms.

## 2026-10-18 Stall 5 m / 8 m results
- **Stall 5 m vs 3 m (paired):** tuning +0.023 [+0.013, +0.034] (W19 / L1); **held-out +0.011 [-0.000, +0.023]** (W15 / L2; new: 1 collision, 1 corridor exit; fixed 1 offroad); fresh 003 +0.012 [+0.004, +0.022] (W5 / L0); fresh 014 timed out in the input stage (part download, 3 h). All but 014: **+0.017 [+0.010, +0.024]**, W39 / L3. Held-out is weaker than for 1 m and 3 m and its interval touches zero, so **5 m is not adopted yet**; 014 rerun with 4 h queued.
- **Stall 8 m vs 5 m, tuning:** -0.000 [-0.009, +0.007], W14 / L2, 2 new zero-score failures (1 collision, 1 offroad). The gain stops between 3 and 5 m; 8 m is rejected.
- Means over the 754 scenes: Q without stall 0.809, Q + stall 3 m (`q:3`) 0.852 (+0.042 [+0.032, +0.054], W57 / L3).
- Fileset at **23 GB free (100%)**; this folder is 207 GB (unchanged: held-out assets, envs, runs).
- **Storage dedupe with the PAI agent (Aman approved 2026-10-18):** the only data both folders held was `data/nuplan_track/nuplan_test` (85,035 files, 4.8 GB) and `navtest/configs` (1,491 files). sha256 of every file on both sides (jobs 13533002 + 13533445, read-only): all identical, nothing extra on either side. Our copies were deleted and replaced with absolute symlinks into `../alpasim/data/nuplan_track/` (all files read back through the links). `sim_nuplan.sbatch` now copies them with `cp -rL` for node-local runs. The PAI agent has the list of `alpasim/` paths we read (simulator/renderer sandboxes, part 001 assets, overlays, scripts, HF token file, the symlink targets) so its cleanups keep them. The scene assets do not overlap (alpasim: part 001, 100 scenes; ours: 468 other scenes). The fileset dipped to 6.1 GB free before the deletion (12 GB after).
- **Tag clash resolved with the PAI agent (2026-10-18):** both tracks had planned `v6`. Agreed: **nuPlan keeps `v6`** (candidate Q, `local/q:3`); PAI takes `v7` (or its still-unused `v5` reservation). Pushed so far per both ledgers: v0.1-starter, v0.2-a15int8, v0.3-a15int8-1hz, nuplan-wajepa-judge-6672747 (the WA-JEPA warmup image, 2026-10-03). Reserved, not pushed: v4 (nuPlan WA-JEPA + judge), v5 (PAI), v6 (nuPlan Q). The PAI agent keeps the register table in `../alpasim/LEDGER.md`. Before any push, list the repo's tags and confirm the tag is absent (a push overwrites).
  - Settled (PAI agent, alpasim commit 80f8104): PAI's next entry is `v5` (route-snap image), nuPlan keeps `v6`, `v7` is a spare for a second PAI entry. The register in `../alpasim/LEDGER.md` now lists all four plus the "list tags before pushing" rule.
- **My error after the dedupe:** fresh run 13532778 (stall 5 m, part 014) was still copying `nuplan_test` to `/local` when the links replaced our copy (copying 85k small files from GPFS takes over 2 h; this, not the HF download, is what made the earlier fresh runs time out). Its copy was incomplete, so it was cancelled and deleted.
- **Fixes in `sim_nuplan.sbatch`:** (1) fresh-part runs symlink `nuplan_test` / `navtest/configs` into `../alpasim` instead of copying them (removes the 2 h copy); (2) the simulator services only see explicit binds, so `$A/data/nuplan_track` is now passed as `--extra-bind` (read-only) whenever the track root is not that directory itself, so the symlinks resolve inside the containers. The first link-check sim (13534105) used the old script and was cancelled; a 3-scene check with the fixed script is running (13534747), compared against `qstall3m1` on the same scenes.
- Fileset hit its quota at 15:37 (PAI agent's report); none of our jobs were affected. Finished runs keep 24-34 MB; running sims hold a few GB of raw logs until slimming, so one sim at a time.
- **Link check passed (13534747):** 3 scenes of shard 010 through the symlinked `nuplan_test` / `configs` with the extra bind: runtime exit 0, all 3 scores equal to `qstall3m1` (1.0 each). Stall 5 m on fresh part 014 resubmitted with the no-copy script.
- **Stall 5 m, fresh 014 (13536496, no-copy script):** vs 3 m -0.002 [-0.008, +0.003], W3 / L1, 1 new offroad. Fresh 003+014: +0.005 [-0.000, +0.010]. **Held-out + fresh (454): +0.008 [+0.002, +0.016], W23 / L3, new zero-score failures 3 (corridor, collision, offroad) vs 1 fixed.** All 754: +0.014 [+0.008, +0.020], but most of it is tuning (+0.023), the set the threshold was chosen on; the gain shrinks on held-out (+0.011) and fresh (+0.005) and adds failures. **Decision: keep 3 m (`q:3`)**: the unseen-scene gain is small and trades progress for 3 new zero-score scenes, the pattern of a knob tuned past what generalises. 5 m stays documented as the alternative.

## 2026-10-20 Fine-tune A31 (Aman approved)
- **Submitted 13569405:** same as fine-tune A (public `model_0014` init, 430 logs at `OFFSET=0`, node-local data, `-c 10 --mem=100G`) except **31 epochs** (cosine restarts: cycle ends at epochs 15 and 31); keeps `model_0014` (epoch 15) and `model_0030` (epoch 31). Expected ~5.3 h data + ~2 h training (A: 3.7 min/epoch after compile).
- Plan: closed loop with the Q recipe (judge m3 R3 + time warp + stall 3 m), paired against `qstall3m1` (= `q:3`): epoch 31 on tuning first; then held-out and fresh if positive. Epoch 15 of A31 vs A as a reproducibility check (same data, init and schedule up to epoch 15).
- Fileset 86 GB free (99%) at submission.
- **A31 trained (13569405, A6000 node ins094, 8.9 h):** data 4.3 h (362 train + 68 val logs, 108,414 samples, the same as A), training 4.5 h (31 epochs / 52,483 steps; slower per epoch than A on the R6000 node). Kept `model_0014` (epoch 15) and `model_0030` (epoch 31) in `runs/py123d_local_ftA31_13569405`. Closed loop with the Q recipe (stall 3 m) on tuning queued: epoch 31 (13602733-35) and epoch 15 (13602736-38), each paired against `qstall3m1`. Fileset 428 GB free (92%).
- **A31 closed loop, tuning (Q recipe with stall 3 m, paired vs `qstall3m1` = `q:3`; 13602733-38):** epoch 31 **-0.003 [-0.016, +0.011]**, W32 / L33 (001 +0.008, 010 -0.002, 005 -0.013); epoch 15 +0.004 [-0.012, +0.020] (W39 / L28; same training as A up to epoch 15, so this is run-to-run noise: the run is sound); epoch 31 - epoch 15: -0.006 [-0.022, +0.009]. Means: q:3 0.872, A31 e15 0.875, A31 e31 0.869. **Longer training gives no gain; not taken further (held-out and fresh not spent). `q:3` stays.** Consistent with A2: once the judge + stall rescue sit on top, more fine-tuning of the base no longer moves the closed-loop score.

## 2026-10-21 Submission decision brief (with the PAI agent)
- **Slots:** 2 of 3 October official left (PAI `v5` used one today: PCS 2184, scene 0.652, 4th team overall; prize-eligible order ACM 2256, VAIL 2230, us; team-rvs is host). Warmups: nuplan-warmup 1 left.
- **nuPlan board (2026-10-21, 139 entries, read by the PAI agent):** hosts (py123d-garage) hold most of the top 14 and are prize-ineligible. Best eligible: **SymPhi 1920 (scene 0.944, at-fault distance 0.875)**, then Lucifer AI 1710 (0.890 / 0.528). Ours: v0.3 rank 40 (0.827 / 0.234). PCS seems to weigh at-fault distance heavily.
- **q:3 local vs public py123d (754 scenes, paired):** **+0.128 [+0.108, +0.149]**, W212 / L52 (tuning +0.110, held-out +0.123, fresh +0.162). Local means 0.852 vs 0.724; public is 0.848 officially, so q:3 expected **~0.91-0.93** official scene score. Failures: offroad 105 → 36, collisions 11 → 12, corridor 15 → 13; at-fault km per collision 1.64 → 1.74 (safety unchanged; the gain is offroad + progress).
- Expected: about 2nd among prize-eligible nuPlan teams; P(#1 eligible) ~15-25%.
- Rules (Space, 2026-10-21): award-eligible nuPlan entries may use only public data and weights (q:3: public py123d checkpoint, public nuPlan data, public GTRS checkpoint: OK); top 3 teams per track get final runs (nuPlan: 2 extra runs); one final container per track; a 4-page technical report per track by Oct 31 is required for awards.
- **`v6` pushed (Aman, 2026-10-21):** `teams/amanupg:v6`, digest **sha256:0d13aceb9285c368271f057b32914a8cc01b04f2e6e00b669d3e57c5fef14871** = `local/q:3` (the closed-loop-verified image). Before the push: `limits` 2 official / 1 nuplan-warmup left; `ecr-login` OK; `v6` absent from the registry. Push took several hours (no shared layers). Not yet submitted.
- **`v6` warmup submitted (Aman, 2026-10-21 19:12 UTC):** track `nuplan-warmup`, submission_id `4b849e1d-970a-496a-8fb1-2d7a996033f3`, QUEUED 2/2. Last nuPlan warmup of the 30-day window; no official slot used. Official submit follows if it succeeds.
- **`v6` warmup SUCCEEDED (4b849e1d, 20:25-20:37 UTC):** resolved digest `sha256:0d13aceb…` (the verified image), 32/32 rollouts valid and scored, wall time **268.5 s of 2,700 s** (throughput check passed with a 2,431 s margin). Ready for the official nuPlan submit.
- **`v6` OFFICIAL nuPlan submission (Aman, 2026-10-21):** submission_id `9ec0413f-42e9-4cf0-9c27-d5380339fa84`, QUEUED 1/1, default controller gains. October official slots: 1 left after this (shared with PAI; held until ~Oct 27-28 for whichever track has the better shot at #1).

## 2026-10-21 **v6 official result: scene 0.782, PCS 1131, rank 48 — worse than v0.3 and the public checkpoint**
| nuPlan official | PCS [95%] | rank interval | scene | at-fault distance | dist to GT |
|---|---|---|---|---|---|
| public py123d 0014 (other teams' entries) | ~1485 | | 0.848 | | |
| our v0.3 (Alpamayo, 09-29) | 1298 [1233-1363] | 37-44 | 0.827 | 0.234 | 1.278 |
| **v6 = q:3 (9ec0413f)** | **1131 [1076-1186]** | **46-60** | **0.782** | 0.324 | **1.766** |
| SymPhi (best eligible) | 1948 | 1-5 | 0.944 | 0.875 | 0.747 |
| nuVAIL (new 10-21) | 1858 | 1-10 | 0.947 | 0.675 | 0.556 |
| Lucifer AI | 1711 | 7-20 | 0.890 | 0.528 | 0.737 |
- Run: 1000/1000 rollouts, 1,189 s of 3,000 s. The image was correct (verified digest).
- **Expected ~0.92 from local; got 0.782 (-0.066 vs the public checkpoint our local said we beat by +0.128).** The local gain was dominated by components (GTRS-Dense critic, time warp, stall rescue that defers to the critic) whose family this ledger already showed to be flattered by public navtest: on 2026-10-02, SimScale GTRS scored 0.53-0.76 officially vs 0.73-0.89 locally, and every NAVSIM-trained driver ranked below go-straight officially. I applied the local gain anyway; that was the error. dist_to_gt 1.77 (vs 0.6-0.75 for py123d entries, ~2.2 for the NAVSIM samples) points the same way: the critic's substituted paths and the warp pull the car off the recorded path.
- **Lesson (hard rule from now on):** local navtest gains from anything NAVSIM-trained or navtest-tuned do not predict the official score. Only components trained on nuPlan train/val (like the fine-tune alone) have a chance of transferring, and even they need an official data point before being stacked.
- Not knowable from this one run: how much of the loss is the critic vs the time warp vs stall rescue, and whether the fine-tune alone helps officially.
- **Time-warp breakdown for the PAI agent (local navtest, plain public py123d ± warp, paired):** 1.10 on all plans -0.014 (stop-go scenes where the driver went 5-30 m: +0.034, W54 / L5, 27 partial → pass; moving urban 30-80 m: -0.058, pass → offroad 6, → corridor 4: corner cutting); 1.10 straight-only (<10°) +0.009, W80 / L11 (slow +0.021, urban -0.002); 1.25 on all -0.108 (22 pass → at-fault collision: gap closing). Precision check prompted by the PAI agent's bf16 AdamW finding: our fine-tunes are safe (py123d bf16-mixed with fp32 master weights; WA-JEPA route params fp32 under autocast). Leaderboard lists every submission; final standing uses the container selected by Oct 31.
- **2026-10-21 Aman: nuPlan is out of the picture; focus entirely on PAI.** The nuPlan thread stops here: no further nuPlan jobs or submissions. The last October slot belongs to PAI. If a final nuPlan container must be selected by Oct 31, `v0.3` (0.827 / PCS 1298) is better than `v6`.

## 2026-10-23 nuPlan back on; PAI FlashDrive bet handed off
- **Organisers (email 2026-10-23):** nuPlan submissions and report deadline moved to **2026-11-16** (AoE); 3 official submissions in November via the monthly reset (PAI closes 2026-10-31, so effectively nuPlan's); winners targeted 2026-11-23 for nuPlan; innovation award may also consider the end-of-October leaderboard; first place and innovation winners must make a 3-min video by 2026-12-03. Reason: py123d_garage v0.2.0 released ~2026-10-22 (issue #221).
- **Aman: "nuplan is back on"**, and the work split is restored: this thread is nuPlan only; PAI belongs to the alpasim/Alpamayo agent, which received the full FlashDrive state (code `pai_flashdrive/`, weights `weights/flashdrive/`, prebuilt kernel, open-loop results: A6000 11.6 GB, 884 ms/plan non-streaming, ADE 1.09 m; checks 13639629-30 handed over).
- **py123d_garage v0.2.0/v0.2.2:** four 68M camera-only Latent TransFuser variants (base-joint32/64, base-waypoints, streaming-joint64), 3 seeds each, pretrain / midtrain / posttrain stages, flow-matching planner (64 waypoints over 6.4 s + actions + 64 m path), front camera only on nuPlan (current + 1 s earlier), up to 3 route target points at 40/60/80 m, 2 Hz replanning (earlier leaderboard entries replanned at 10 Hz), seed ensembles (plans averaged), submission scripts (`scripts/alpasim_submission/*`, TRACK=nuplan). Trained on PAI AV + NuRec + nuPlan train/val (not navtest). Model card `ltf-base-joint64-68M`: local nuPlan (1,485 navtest scenes) 91.4 ± 1.0, 0.747 km/incident, offroad 3.3 %, collision 0.2 %, corridor 0.0 %, progress 88.7.
- **nuPlan board 2026-10-23 (147 entries):** SymPhi 1932 (0.950 / 0.875), host 093-nuplan-v1 1918 (0.944 / 0.981), host 092 1885 (0.932), nuVAIL 1853 (0.951 / 0.675), Lucifer AI 1664 (0.893). No v0.2.0-style team entries visible yet besides the host's.
- **Candidate N1 (`local/n:1`, image id `0a06ba20a19c`, 12.6 GB):** `container/Dockerfile.n` = py123d's v0.2.2 submission Dockerfile (uv from PyPI) with the released v0.2.0 `ltf-base-joint64-68M/posttrain/model_0.pth` (sha256 d7113ef3…, = HF), its config and `sensor_rig_nuplan.yaml`, alpasim_grpc 0.54.0 built from NVlabs/alpasim e2e_challenge @ e121e59 (py123d's pinned commit), `NOTICE.n`. All Apache-2.0, public. Planned for the first November slot (Nov 1): the released model as is, for an official calibration point of the v0.2 family.
- `sim_nuplan.sbatch`: `imagep` now runs the image's own module (py123d v0.2 images have no `garage_addons`); new `DRIVER=garage2` runs py123d v0.2.2 natively from a node-local env (`cluster/garage2_env.sh`) for fast A/B of checkpoints (`G2_CKPTS`, several = ensemble) and driver settings (`G2_OVERRIDES`).
- **Queued:** n:1 image on tuning 001/010/005 (after upload; checks the exact image runs in our harness); garage2 on tuning: seed 0 (13640575-77; must match the image), 3-seed ensemble (13640578-80), seed 0 + route_memory (13640581-83). Local numbers are for same-family comparisons only; N1's official result will be the first calibration of local vs official for v0.2.
- **n:1 image in our harness, shard 001 (13641296, imagep):** 100/100 sessions, checkpoint hashes inside the image = released files; local mean **0.935** (2 zero-score scenes, both offroad). Paired: vs public 0014 **+0.148 [+0.098, +0.201]**; vs the v6 recipe (qstall3m1, 0.782 officially) +0.032 [-0.009, +0.076]. Local only: the official N1 result is the calibration. (Unlike v6's critic, v0.2.0 was not trained on navtest.)
- v0.2.0 fetch job 13640496 failed on a Xet transfer error after the joint64 posttrain files had arrived (hashes = HF); garage2 runs resubmitted without the dependency (13646109-17).
- **Tuning shards 001/010/005 (300, paired, local):** n:1 image **0.908** vs public 0014 0.761: **+0.147 [+0.114, +0.182]**, W96 / L17 (fixes 24 offroad + 5 corridor, adds 3 offroad + 1 corridor); vs the v6 recipe +0.037 [+0.013, +0.061]. garage2 seed 0 vs the n:1 image (010+005): +0.001, 175/200 identical (different GPU types). 3-seed ensemble vs seed 0 (010+005): +0.010 [-0.009, +0.030], W19 / L16, inconclusive. route_memory vs seed 0: +0.000 (no effect). garage2 seed 0 on 001 failed (runtime service exit 1 on ins048, infra); rerun queued with seed 0 and the ensemble on held-out 013/007/011.
- **Published per-seed nuPlan results (kesai, 1,485 navtest scenes, 2 Hz):** joint64 s0 0.917, s1 0.904, s2 0.923; joint32 0.908 / 0.904 / 0.898; waypoints 0.895 / 0.902 / 0.892; streaming-joint64 0.909 / 0.898 / 0.903. joint64 is the best variant. Paired (excluding the 10 route-foldback scenes): s2 - s0 +0.006 [-0.002, +0.014] (n.s.); s0 - s1 +0.013 [+0.005, +0.021]; s2 - s1 +0.019. N1 stays seed 0 (the released default); a seed 0 + 2 ensemble (leaving out the weaker seed 1) is a later candidate.
- **Next lever: nuPlan-only fine-tune of v0.2.0.** py123d v0.2.2 has a `latent_transfuser:nuplan_posttrain` preset (front camera, nuPlan train/val sources, backbone frozen, target-point dropout). Plan: start from joint64 posttrain model_0, ~7 epochs (the model card's fine-tune recipe), one seed, node-local data and cache; then WiSE-style averaging with the base (the PAI agent's 0.5/0.5 average gave +0.049 on PAI).
- **Storage (fileset at 61 GB free):** deleted the n:1 archive (12.6 GB; its 3 harness runs were done, the image stays on the Mac) and, with Aman's approval, the FlashDrive weights (32 GB; FlashDrive is parked by the PAI agent; code and prebuilt kernel stay in `pai_flashdrive/`, weights re-downloadable from z-lab in ~15 min).
- **v0.2 fine-tune smoke run queued (13647157):** 30 logs, 1 epoch, nuplan_posttrain preset from joint64 posttrain model_0, front camera only, hf_xet downloads.
- **v0.2 fine-tune pipeline works (smoke 13647550, A6000):** env (+ train extra, wandb/protobuf pinned, wandb off), 30 logs front camera fetched + cached in 8 min (5 GB), strict load of joint64 posttrain model_0, 53,789 samples, 1 epoch = 840 batches in 3.6 min (~245 samples/s after compile, `compile=reduce-overhead`). Fixes on the way: absolute uv path, `--extra train`, wandb 0.30.0 + protobuf 7.36.2, `wandb_config.enabled=false`.
- **Full fine-tune ftN submitted:** NLOGS=400 (OFFSET 0), EPOCHS=7, DATA_HOURS=3, nuplan_posttrain from joint64 posttrain model_0; ~2 h data + ~1 h/epoch expected on one A6000. Then WiSE averages (0.5, 0.3) with the base, all evaluated paired against seed 0 on tuning, then held-out.
- **3-seed ensemble (plans averaged) vs seed 0, garage2:** tuning (300) +0.007 [-0.006, +0.020], W27 / L20; held-out 007+011 (161) -0.019 [-0.045, +0.006], W14 / L12. No gain: dropped. (Seed 0 on 013 failed at start-up, rerun queued as the fine-tune baseline.)
- **WiSE averaging script (`src/analysis/wise_average.py`) tested** on the smoke fine-tune: 768 float tensors averaged, 76 kept from the base. The released v0.2.0 file holds 4 planner normalization constants that v0.2.2 checkpoints omit (the v0.2.2 strict load accepts the released file), so they are kept from the base; a tensor only in the fine-tuned file would be an error.
- **ftN attempt 1 (13647603) failed at the first training step** after a clean data stage (400 logs: 362 train + 38 val, 497,784 samples, 66 min): PyTorch caching-allocator assert `curr_block->next == nullptr` with `expandable_segments:True` + compile=reduce-overhead (CUDA graphs). The smoke run had survived the same setting. Resubmitted without expandable_segments (13647809); one epoch is 7,777 batches (~35 min at the smoke run's speed), so ~5 h in all.
- garage2 seed 0 on held-out 013 rerun completed (13647621): the held-out baseline for the fine-tune comparison is complete.
- **ftN attempt 2 (13647809)** trained ~960 batches at ~4.0 batches/s (~260 samples/s), then segfaulted in the optimizer step inside `cudagraph_trees` replay (compile=reduce-overhead). Attempt 3 uses `compile_mode=default` (no CUDA graphs).
- **ftN attempt 3 (13647888)** died in the data stage after batch 26's cache: the prefetched batch 26 had already been cached by batch 25's run, so `grep "Cached"` found nothing and `set -e` ended the job (my script bug, latent in the v0.1 script too; fixed in both). Attempt 4 submitted.
- **ftN trained (13648035, A6000 ins093, 3.5 h):** 400 logs (362 train + 38 val), 497,784 samples, 7 epochs / 54,439 steps at ~6.3 batches/s (402 samples/s; compile_mode=default ran faster than reduce-overhead had), kept epochs 1/3/7 (`model_0_0000/0002/0006.pth`) in `runs/py123d_v2ft_ftN_13648035`. WiSE blends of epoch 7 with the released seed 0: alpha 0.5 and 0.3 (13648333); tuning evals (garage2, released nuPlan rig) of the fine-tune alone (ftN100), wise050 and wise030 queued (13648334-42), paired against garage2 seed 0.
- **ftN on tuning (garage2, paired vs released seed 0, 300 scenes):** fine-tune alone -0.012 [-0.030, +0.004] (W29 / L31); WiSE 0.5 +0.000 [-0.013, +0.013] (W31 / L16); WiSE 0.3 +0.001 [-0.011, +0.012] (W31 / L12). **No gain: nuPlan-only fine-tuning of v0.2.0 dropped** (it was already trained on nuPlan; same pattern as A2/A31 on v0.1).
- **Next lever, replan rate:** py123d v0.2 replans at 2 Hz (`replan_interval_us=500000`); the release notes say its earlier leaderboard entries (host 093: 0.944, at-fault 0.981, the board's best safety) replanned at 10 Hz. Tuning runs at 10 Hz and 5 Hz queued, paired against 2 Hz seed 0.
- **PAI agent's controller-gain findings (Alpamayo, PAI, local):** nothing beat noise; no gain was ever submitted. lat 3 / heading 2: +0.002 [-0.051, +0.056] (40 scenes); lat 5 / heading 3: -0.015; idx_start_penalty 5 (default 10, i.e. down): -0.040 [-0.090, -0.001], mostly offroad. Untested there: acceleration_weight, long_position_weight, idx_start_penalty up. Their first gain reads were invalid from shared gRPC ports between co-located jobs; our sim_nuplan already uses a per-job port block, and nuPlan MTGS reruns on one GPU type are bit-identical, so our noise is scene sampling only.
- **Replan rate (garage2, tuning 001+010, 200 scenes, vs 2 Hz seed 0):** 10 Hz -0.006 [-0.016, +0.000] (W8 / L15, 1 new offroad); 5 Hz -0.000. 2 Hz stays (005 runs died in the disk-full below).
- **2026-10-24 13:30 the dept fileset filled up (640 MB free)**: my two 005 runs failed on writes (exit 120). Cause: the PAI folder's fresh-scene fetch (150 GB of NuRec usdz); the PAI agent freed 97 GB with Aman's approval and now stages scenes node-local (LOCAL_FS=1). On my side, with Aman's approval, deleted the WA-JEPA v4 sandbox (`sandbox/wajepa-v2`, 8.8 GB; the image stays on the Mac and in the registry) and the rejected v0.1 fine-tunes A2 and A31 (2.4 GB); also my own temp dirs (v0.2 smoke run, the 2 failed runs). Kept: uv cache, sim run dirs, fine-tune A (q:3's source). No other folder referenced the deleted paths (grep over alpasim, jepa-nureasoning, nureasoning, wearable).
- **MPC gains on v0.2.0 (garage2 seed 0, tuning 300, paired vs default gains; overrides confirmed in each run's wizard-config):** lat_position_weight 2.0: -0.000 [-0.008, +0.007], W17 / L21; **idx_start_penalty 15: +0.004 [+0.002, +0.006], W29 / L9, no new zero-score scenes** (small, consistent). It is a submission-time setting (no image change) and the controller is not navtest-trained, so it is a plausible transfer. Queued: idx 15 on held-out 013/007/011, idx 19 (the allowed maximum) on tuning.
- **idx_start_penalty 15, held-out 013/007/011 (261):** -0.014 [-0.026, -0.002], W26 / L8, **4 new zero-score scenes** (offroad 2, collision 1, corridor 1). Many small progress wins, a few scene-killing failures: the same pattern as stall 5 m. **Not adopted.** idx 19 on tuning: +0.012 [+0.006, +0.020], W32 / L7, no new failures; queued on held-out to settle it.
- **idx_start_penalty 19, held-out (261):** -0.010 [-0.024, +0.003], W28 / L6, the same 4 new zero-score scenes as idx 15 (offroad 2, collision 1, corridor 1). **Not adopted; MPC gains stay default.** Every v0.2.0 lever tried so far (ensemble, nuPlan fine-tune ± WiSE, replan rate, lateral weight, idx_start_penalty) fails to beat the released model on unseen scenes.
- **Next v0.2.0 levers: the policy's own inference options** (designed by its authors, not trained on navtest, no retraining). `finalize_evaluation` re-applies `policy_config.*` overrides over the checkpoint's saved config, so the driver accepts them. Queued on tuning (13655908-19), paired vs default (waypoints, 8 steps): `flow_config.driven_output` = actions / waypoints_on_path / actions_on_path, and `num_inference_steps` = 16. Others in reserve: `test_time_target_point_distances_m`, `noise_temperature` + `num_averaged_samples`.
- **Inference options on tuning (13656835-46, paired vs default seed 0; overrides need a `+` prefix, which finalize_evaluation strips; the first batch failed without it, the second on node ins037: exit 0:53, no log, now excluded):** driven_output=actions +0.002 [-0.005, +0.007] (W28 / L11, 1 new offroad); waypoints_on_path -0.007 [-0.018, +0.002] (3 new offroad); actions_on_path -0.004 [-0.014, +0.006] (3 new offroad); num_inference_steps 16 -0.002 [-0.004, -0.000]. **None adopted: the released defaults are already the best combination.**
- Queued on tuning: seed 2 alone, seed 0 + 2 ensemble, no target points at test time, 40 m target point only.
- **Seeds / target points on tuning (13657384-95, garage2, paired vs seed 0, 300 scenes):** seed 2 alone +0.003 [-0.013, +0.018] (W29 / L22, 2 new offroad); **seed 0 + 2 ensemble +0.010 [+0.002, +0.019], W26 / L19, no new zero-score scenes** (fixed 1 collision, 1 offroad); no target points -0.017 [-0.035, -0.001] (7 new failures); 40 m target only +0.000 (264/300 identical). The 0 + 2 ensemble is queued on held-out 013/007/011 (13658178-80). The 3-seed ensemble was tuning +0.007 and held-out -0.019, so this needs held-out before anything.
- Queued on tuning (13658184-89): flow sampling with averaged draws, `noise_temperature` 1.0 and 0.5, each with `num_averaged_samples=8` (default: one draw from the zero state).
- **Seed 0 + 2 ensemble, held-out 013/007/011 (13658178-80):** -0.009 [-0.024, +0.005], W21 / L16, **4 new zero-score scenes** (offroad 2, collision 1, corridor 1), none fixed. Same as the 3-seed ensemble: tuning-positive, held-out negative. **Dropped.**
- **Averaged flow samples, tuning (13658184-89):** noise_temperature 1.0 x 8 draws -0.016 [-0.032, -0.001] (W9 / L37, 6 new failures); 0.5 x 8 -0.015 [-0.028, -0.005] (W10 / L31, 4 new). The zero-state single draw (default) is best. **Every v0.2.0 inference option is now tested; the released defaults win.**
- **nuPlan board 2026-10-25 (154 entries):** nuVAIL `nu-vail-2` (submitted 10-25) **2016**, scene 0.974, at-fault 1.43 km/incident; host 093-nuplan-v1 1979 (0.944 / 0.98); SymPhi garage-ltf-v6c10 2001 (0.950 / 0.87); nuVAIL run6-soup23-argmax 1906 (0.951 / 0.68). Ratings are relative and shift as entries arrive (SymPhi 1932 → 2001, host 093 1918 → 1979 since 10-23). The bar to win moved up: ~0.97 scene score with ~1.4 km between at-fault incidents.
- **Research sweep 2026-10-25 (web; sources in the agent report):** no public method from nuVAIL (possibly SNU VAIL, low-medium certainty), SymPhi or the host's 093/092. Organizers (NVlabs/alpasim#221): no further nuPlan-applicable releases before Nov 16; py123d HF has only v0.2.0 weights; v0.2.2 is a pipeline fix. Final runs: top 3 get 2 extra nuPlan runs; results ~Nov 23. Untried ideas in py123d's research log: closed-loop training, input-resolution sweep.
- **Verified: replan rate is a no-op on nuPlan.** The nuPlan control step is fixed at 500 ms (NVlabs/alpasim#155; our runs: `control_timestep_us: 500000`), so 2 Hz already replans every step and `replan_interval_us=100000` changes nothing. The earlier 10 Hz / 5 Hz differences were GPU-type run-to-run noise (a useful noise floor: ~0.006). 10 Hz reruns cancelled (13660889-92).
- **Verified: local nuPlan rendering matches official.** Official nuPlan runs have the Harmonizer off; the `--enable-harmonizer` flag exists only in the NRE (PAI) renderer command, and our nuPlan runs use `alpasim-mtgs-server` without it.
- Queued on tuning (13660903-05): `extrapolate_route=true` (extends a route that ends before the 80 m target point straight along its last heading; the only driver option not yet tried).
- **extrapolate_route, tuning (13660903-05):** -0.003 [-0.013, +0.007], W22 / L17, 261 identical, 2 new offroad. **Dropped.** Every driver/inference option of v0.2.0 is now tested.
- **Rules check (HF page, 2026-10-25):** award-eligible nuPlan entries may use only public data/weights; host entries are excluded from prizes; innovation award open "on any baseline"; top 3 teams get 2 extra nuPlan final runs, Harmonizer off for nuPlan finals. Best non-host teams: nuVAIL 2016 (0.974), SymPhi 2001 (0.950), team-trsue 1701 (0.914), team-lucifer 1663 (0.893).
- **Where seed 0 loses (561 tuning + held-out scenes, mean 0.900):** zero scores 5.5 points (offroad 18, collision 2, corridor 2; plus 8 public route-foldback scenes, which are not in the private set, and 1 corrupt local asset), **partial progress 4.5 points (68 scenes)**. Within the partial ones, **17 scenes stall: the ego never starts (score < 0.2, no failure) while the logged car covers 6-14 m**; several are then rear-ended (not at fault). The stalls persist across every variant (seed 2, ensembles, target points, extrapolated route, sampling, fine-tune), so the model consistently refuses to start there. Released config: speed input on, `speed_dropout_probability: 0` (no learned null speed). Diagnostic reruns of the 17 stall scenes with plan logs and per-plan video queued (13661475-76).
- **Stall diagnosis (plan logs of the 17 stall scenes, 13664147-48; all 17 reproduce):** the ego starts at rest (speed 0.00 at the first plan; the log ego pulls away). In **11 of 17 the policy plans "wait 1.7-4.0 s, then go"** (plan ends 14-40 m away) **at every replan**: the first ~16-40 poses (0.1 s each) stay within 0.3 m. The MPC tracks only the next 2.5 s, all waiting, so the ego never moves: a receding-horizon "always later" start. In the other 6 the plan itself stays stopped (ends < 3 m).
- **New add-on `src/g2_addons/entry.py`** (wraps py123d v0.2.2's `GarageDriver._plan`, no code changes; `sim_nuplan.sbatch` `G2_MODULE=g2_addons.entry`): **start-now**: when the ego is stopped (< 0.5 m/s) and the last K plans were already wait-then-go (motion after >= 0.5 s, plan end >= 3 m), drop the waiting prefix of the next one so its motion starts now (tail extended at constant velocity). Plans that stay stopped are never touched. Rule logic, no learned or NAVSIM component. Offline check on the logged plans: 11 shifted (first 0.5 s ~0.7 m), 6 untouched. Tuning runs K=1 and K=3 queued (13664630-35), paired vs seed 0. Risk to watch: collisions when the wait was real (crossing traffic).
- **Start-now, tuning (13664630-35, paired vs seed 0, 300):** **K=3 +0.012 [+0.005, +0.020], W16 / L10, big W4 / L0, no new zero-score scenes**, any-collision 6 → 4, 16 rescues; K=1 +0.013 [+0.003, +0.024], W22 / L6, big W6 / L1, 1 new at-fault collision, 48 rescues. Queued: both on held-out 013/007/011 (13666134-39) and on fresh parts 003/014 with a seed 0 baseline there (13666140-45, LOCAL_PART).
- **Start-now, held-out + fresh (13666134-45, paired vs seed 0; fresh 003/014 with its own seed 0 baseline):**

| | tuning 300 | held-out 261 | fresh 193 | all 754 | new zero-score | any-collision (all) |
|---|---|---|---|---|---|---|
| **K=3** | +0.012 [+0.005, +0.020] | +0.013 [+0.005, +0.022], W13 / L3 | +0.022 [+0.009, +0.038], W9 / L0 | **+0.015 [+0.009, +0.021]** | **0** | 19 → 13 |
| K=1 | +0.013 [+0.003, +0.024] | +0.022 [+0.008, +0.038], W16 / L4 | +0.031 [+0.015, +0.049], W11 / L0 | +0.021 [+0.013, +0.029] | 2 at-fault collisions | 19 → 12 |

- **Adopted: start-now K=3** (positive on tuning, held-out and fresh, CI > 0 on each, no new zero-score scenes; rule logic, no learned or NAVSIM component; more distance with no new at-fault incidents can only help the at-fault metric). K=1 gains more but adds 2 at-fault collisions in 754 scenes, which also costs the safety metric; kept as the documented alternative. Not tuned further (all three sets are now used).
- Next: image `local/n2:1` = `local/n:1` + `src/g2_addons` with `G2_START_K=3`; verify on the cluster from the archive (IMAGE_ARCHIVE) paired against the garage2 K=3 runs.
- **Image `local/n2:1` built** (`container/Dockerfile.n2`, NOTICE.n2): FROM `local/n:1` + `/opt/addons/g2_addons`, `ENV G2_START_K=3 PYTHONPATH=/opt/addons`, ENTRYPOINT `python -m g2_addons.entry` (same config string as N). Checked inside: START_K 3, checkpoint sha d7113ef3 (released seed 0). Id sha256:5ea4001e…, 12.6 GB. Archive uploading to the cluster for an IMAGE_ARCHIVE verification run (imagep, IMAGE_MODULE=g2_addons.entry) paired against the garage2 K=3 runs. Tag: next free neutral tag after checking the registry (not pushed).
- **Tag:** the PAI agent confirmed **v8 = nuPlan** (recorded in ../alpasim/LEDGER.md's register; PAI's final is v7). Re-list the registry tags right before any push. The PAI agent sees ~10 PAI scenes where the ego never starts after handover (filed as signal compliance) and will check its plan logs for the same wait-then-go pattern.
- **N2 image verified (13668565-67, imagep from the archive, IMAGE_MODULE=g2_addons.entry, tuning 300):** log shows `start-now K=3`, 16 rescues (= garage2 K=3), checkpoint sha d7113ef3 (released seed 0). vs garage2 K=3: -0.001 [-0.003, +0.000], 280/300 identical (GPU-type noise); **vs seed 0: +0.011 [+0.003, +0.020]**, no new zero-score scenes. **`local/n2:1` is the nuPlan candidate, tag v8.** Archives deleted (cluster and Mac).
- **Remaining zero-score scenes with start-now K=3 (22 of 561 tuning + held-out; plan logs + videos 13668837-38):** a log-replay control (`runtime.simulation_config.force_gt_duration_us=30000000`, ego follows the log for the whole scene; 13669006-07) scores 1.0 on 17 and 0 on 5. **The 5 are unavoidable** (offroad at the first step, 0 m driven: 4 in log 2021.09.16.19.27.01_veh-45_01749_03230 and 1 in 2021.09.29.19.02.14_veh-28_01717_01824; public-map artifacts). **17 are real model errors:** 13 offroad, 2 at-fault collisions, 2 corridor exits. Typical pattern (video of 00472_00711-132d): the ego tracks its lane well, then drifts 0.2-1 m to the outside at a bend or lane split; max lateral distance to the log 0.2-1.0 m in the offroads. That is ~3 points of local score; MPC lateral weight did not move it (2026-10-24), so the fix is likely in the policy (closed-loop data on drift) rather than in a rule.
- **Closed-loop build (Aman: "go ahead with the closed-loop build", 2026-10-26):**
  - `src/g2_addons/collect.py` (`G2_MODULE=g2_addons.collect`, training data only, never in an image; `entry.py` unchanged): runs start-now K=3 and records per plan the policy's exact inputs (features + navigation), ego pose/speed/time, and the logged ego trajectory (`runtime.simulation_config.send_recording_ground_truth=true`, a local switch; official runs keep it off). `G2_PERTURB_P/M`: DART-style lateral offsets on served plans (ramp to U(-M, M) over 1.5 s) so states leave the log.
  - `src/closed_loop/labels.py`: recovery labels in py123d's format (trajectory 64x(x,y,yaw) at 0.1 s, path 64 points at 1 m): project the ego on the log (s0, lateral e, heading error), pick the logged time at s0 closest to the anchor, ease e and the heading error to 0 over max(8 m, 2 s x speed). Synthetic checks: 1 m offset eases back over 10 m; a log stop is kept only as long as the log waited; a stuck ego whose log already left gets "go now".
  - `src/closed_loop/train_decoder.py` + `cluster/cl_train.sbatch`: builds the policy like the driver, freezes everything but `planning_decoder`, trains with py123d's own flow loss/weights and `_forward_heads` training conditioning; reports sampled-waypoint L1 to the recovery labels on held-out scenes before/after.
  - Data: the 7 public MTGS parts none of our evaluation sets use (002, 004, 006, 008, 009, 012, 015; ~650 scenes), collected node-local.
- **2026-10-26/27 fileset incident:** from ~17:00 small-file access on the dept fileset slowed ~10x+ (0.75 s per file open; big-file reads stayed fast; fileset 100%, 8-11 GB free, not from our jobs). The MTGS renderer's UnifiedDataset scan of the 85k-file trajdata cache went from 4.5 min to > 40 min: 4 nuPlan jobs (3 nodes) timed out, incl. a plain control, and a 6 h tar of the shared cache timed out. **Fix:** `cluster/fetch_nuplan_cache.sbatch` stores the two public archives the cache ships as (OpenDriveLab HF `trajdata_cache/nuplan_test.tar.gz` 2.17 GB sha 3a87fffa…, `MTGS_asset/navtest/configs.tar.gz` sha 9c93aa6a…; 2:43 to download) in `data/nuplan_cache_hf`; `sim_nuplan.sbatch` LOCAL_CACHE (default on) extracts them to the node's /local (~35 s) with assets symlinked in place. Control run: 2.6 min total, scores identical to the shared-cache seed 0 runs (0.0 / 0.159 / 0.008). The PAI agent was told (its jobs mostly read big files).
- **Collection smoke (3 tuning scenes, discarded):** records align (ego = log within 0.00 m while forced on the log), labels as designed (a stalled ego whose log left gets "go"). Fixes: perturbations now last 3 plans (1.5 s; one 0.5 s plan moved the ego < 2 cm laterally) and skip plans that stay put; camera features stored as JPEG q95 (~10x smaller). The logged trajectory the runtime sends covers only the scene's 5.5 s, so records late in a scene are skipped (label would be > 3.4 s extrapolation).
- **Collection launched (13675395-401):** parts 002 (first), then 004 006 008 009 012 015 after it, LOCAL_PART all scenes, start-now K=3, perturb p=0.3 M=1.0 x 3 plans, captures to `runs/cl_data/part<P>`.
- **Collection done (2026-10-27 07:34):** parts 002/004/008/009/012 100 scenes each, 006 97, 015 90 (687 scenes) in `runs/cl_data`. Trial training on part 002 (13675457, 4 min) ran end to end: 561 of 1,000 plans usable, 83 off-log; label checks on the Mac: labels follow the log through the target points, the released model's plans run ~1.2 m behind the label at 2.5 s and turn back slowly after drifting.
- **2026-10-28: paused on Aman's request ("pause any runs on insomnia till oct 31 ... going all in on pai").** No nuPlan job queued or running (all queued jobs are the PAI agent's `as_*`). Nothing of ours resumes on Insomnia before Nov 1. Next on Nov 1: decoder training on the 687 scenes (needs Aman's go), then closed-loop evals vs v8; Aman submits v8 on Nov 1.
- **2026-11-04: PAI closed; lessons file read** (`../LESSONS_FOR_AGENTS.md`: PAI v7 beat v5 on every visible metric yet lost PCS 2226 → 2151; validate against the ranking metric).
- **nuPlan board 2026-11-04 (198 entries):** nuVAIL nu-vail-9 2124 (0.982, 2.37 km), SymPhi sp-1029a 2135 (0.969, 1.77), Lucifer lf-009 2127 (0.945, 1.04), host 093 2119 (0.944), cqupt 2111 (0.941), metamon 2110 (0.940), praise-the-sun ltf-v02 2080 (0.939). PCS is not monotone in the mean (SymPhi 0.969 > nuVAIL 0.982; Lucifer 0.945 > host 0.944). **v8 is not on the board** (our entries: v0.3-a15int8-1hz 1358, v6 1182); CLI session expired (401), so submission status unknown.
- **Local PCS proxy (organisers' `e2e_challenge/local_evaluation/evaluate.py`, Drive-IRT @ 82ddd5a, zoib; 20 of our policies x 552 tuning+held-out scenes, foldback/corrupt excluded; no fallback warnings):** start-now K=3 3.93, K=1 3.99, idx_start_penalty 19 4.00, idx 15 3.93, ens02 3.84, ens3 3.76, seed 0 3.75, WA-JEPA+judge 2.62, v6-era stacks 1.0-2.0, public 0014 0.66. Over 3 fit seeds: K=3 - seed 0 = +0.18 / +0.10 / +0.20 (posterior std ~0.2); K=1 - K=3 = +0.06 / +0.00 / +0.06; idx19 - seed 0 = +0.25 / +0.10 / +0.25. One seed converged to a compressed scale (top saturates). **Caveat:** the population is ours only (7 near-identical v0.2 variants), so scenes that every one of them fails carry no information; the proxy can rank close variants, not predict the board. Notable: idx19 (rejected on held-out mean, 4 new zero scenes) is proxy-positive; to revisit together with K=3.
- **Evaluation-condition check:** local runs mount simulator code from `../alpasim/external/alpasim` at **2023534 (Sep 18)**; the competition runs **e121e59**. The diff is only `1b024f0` (lateral corridor scorer fix, issue #198) + report upload CLI: scoring only, driving identical. Seed 0 had 2 corridor zeros in 552, both real (4-6 m lateral), so local numbers barely move; future runs will use e121e59 (part of the alpasim/ consolidation; plan sent to the PAI agent, pending Aman's OK).
- **2026-11-04 consolidation (Aman: "move OK, token OK", via the PAI agent):** the PAI agent moved (plain mv, same fileset) from ../alpasim into this folder: `data/nuplan_track/nuplan_test` (12,148 top-level entries), `navtest/configs` (1,491), 100 shard-001 asset dirs (B now 568, no overlaps), `sandbox/alpasim-base`, `external/alpasim` → `ext/alpasim_sim` (HEAD 2023534), and the HF token → `.cache/hf/token` (mode 600, sha256 b89a3f89… unchanged). I deleted our two symlinks first and copied `summarize_run.py` / `compare_runs.py` → `src/tools/`, the shard-001 scene list → `runs/scenes_shard001/`. Scripts repointed (`sim_nuplan.sbatch` SIF/REPO/NUPLAN_ROOT/SCENES_FROM/tools/binds; token path in 5 scripts). The rest of ../alpasim on the cluster is deleted by the PAI agent; nothing claimed from its D1-D8 list. The a15 / SimScale-sample / wajepa drivers in sim_nuplan still name the deleted `envs/overlay_driver` (not needed now). Smoke sim from the new paths queued (13792458).
- **Move verified (13792458):** 3 shard-001 scenes, plain seed 0, from the new paths: 0.0 / 0.159 / 0.008, identical to before; no alpasim/ reads in the log. Removed our dangling-to-be symlink `data/fs/nre-artifacts/all-usdzs` (PAI-only). The PAI agent was told deletions can proceed.
- **Closed-loop decoder training round 1 (Aman: "go ahead with the closed-loop training"; 13798308, A6000, 21 min incl. env build):** 687 scenes from parts 002/004/006/008/009/012/015, 3,982 usable records (2,888 skipped: label would need > 3.4 s of extrapolation past the 5.5 s log), 694 off-log (|e| > 0.3 m); train 3,538 / val 444 (77 scenes, by scene). 4 epochs, 444 steps, lr 2e-5 one-cycle, backbone + other heads frozen.
  - **Validity:** loss (total, 50-step windows) 0.335 → 0.270 → 0.242 → 0.237 → 0.229 → 0.218 (falls, mostly in epoch 0); held-out sampled-waypoint L1 to the recovery labels 2.914 → 2.684 → 2.648 → 2.658 → 2.652 m (all), 4.434 → 3.805 m (off-log, n=75); **weights moved little**: decoder relative L2 0.0005 (largest single tensor: flow time embedding 8.9%). A gentle change, so a small closed-loop effect would not mean the idea failed.
  - Closed loop queued (13798876-78): r1 + start-now K=3 on tuning, paired vs `g2sk3` (= v8) on the same simulator commit.
- **Round 1 closed loop, tuning (13798876-78; r1 + start-now K=3, paired vs `g2sk3` = v8, same simulator commit; 11 rescues):** **-0.013 [-0.033, +0.005]**, W29 / L16, big W7 / L9, 255 identical, **9 new zero-score scenes (6 offroad, 3 at-fault collisions)**, 1 fixed; any-collision 4 → 6, at-fault 1 → 4. vs seed 0: -0.001. **Tested properly, no gain** (the change is real: 45 scenes moved, in the risky direction; more small wins, more scene-killing failures). Not adopted; held-out not spent. Likely cause: recovery-to-log labels with log timing make the decoder more assertive (log speed) than the released model, whose caution suits non-reactive replayed traffic.
- **2026-11-05/06 exchange with jepa-nureasoning (Aman asked it to consult us):** gave it read-only pointers to our py123d v0.2.2 checkout, weights and env (it copied them into its own folder; nuReasoning logs 2023-2026 vs nuPlan 2021, so no overlap). Our 5 s distance bias, released posttrain seed 0 vs log at matched nuPlan navtest states (part 002 recordings, on-log, 5 s point inside the log): mean -1.49 m, median -0.66 m (n=96); v >= 8 m/s -0.76 / -0.48 (n=18). **Its zero-shot numbers on real Motional images (1,000 val key frames):** mean +0.38 m, median +0.04 m; v < 3 m/s +2.61 m (starts when the human waits), 3-8 m/s +0.68, >= 8 m/s -1.13 m; distance MAE 5.5 m, lateral 0.48 m at 5 s; inputs verified live. So the released model is not uniformly cautious: from rest its start/wait decision is unstable both ways (here it waits too long in sim, there it goes too early), and at speed it undershoots slightly.
- **2026-11-06, jepa-nureasoning's py123d decoder fine-tune on real Motional images (FYI from that thread):** two folds by drive log (~1,000 rows each), planning decoder only, lr 1e-4 one-cycle, bs 16, 8 epochs. Held-out 5 s distance MAE 5.49 → 4.98 / 5.03 m (best at epoch 1: 4.86 / 5.26); v < 3 m/s bias +2.7 / +2.3 → +0.5 / -0.9 m. Decoder moved 1.1e-3 relative L2 (about 2x our round 1), loss 0.41 → 0.22. Its score: NPS 0.601 vs zero-shot 0.539, still below its own members; no blend value, dropped. **For us:** a decoder-only fine-tune does fix the start/wait bias when the labels are real human timing, but its real-image bias at rest is the opposite sign of ours in sim, so their fine-tune would not transfer; it supports the round-1 reading that the labels' timing drives the behaviour change.
- **2026-11-06, closed-loop round 2: lateral-only labels (Aman: "i still think we should go for it", after the jepa-nureasoning result).** Round 1's labels followed the log's timing; on part 002 they run 36.6 m in 6.4 s vs the model's own plans' 32.2 m (31.8 vs 26.8 before the budget fix below), which fits round 1 getting more assertive (3 new at-fault collisions). Round 2 keeps the policy's own speed profile and corrects only geometry:
  - `labels.recovery_labels(..., timing="own")`: trajectory = distance along the policy's own served plan (collect.py's perturbation ramp removed; steps < 1 cm = still), placed on the eased logged path (same lateral/heading easing as round 1); path label unchanged. Same record filter as round 1 plus the same extension budget in metres (3.4 s x log end speed + 5 m). Part 002: 541 of round 1's 561 records; label end distance within 0.19 m of the plan's (p95 0.89 m); on-log 2 s lateral correction 0.24 m mean.
  - `train_decoder.py`: `CL_TIMING=own`; val now also reports cross-track distance of the sampled plan to the path label (timing-free).
  - Jobs: training 13822069 (`r2lat`, lr 2e-5, as round 1) and 13822070 (`r2lat_hi`, lr 1e-4, the dose that moved jepa-nureasoning's decoder ~2x more); closed loop on tuning s001/s010/s005 with start-now K=3, all on L40S, after each (13822078-80 r2lat, 13822081-83 r2lat_hi); v8 controls on L40S for s001/s010 (13822084-85; v8's own tuning runs were H100 for those two, L40S for s005, round 1 was L40S).
  - Requeued: the A6000 partition put both trainings at Nov 10-11 (ReqNodeNotAvail). Round 1 used 2.6 GB RAM in 21 min, so retrained on any GPU, -c 4, 24G, 1 h: 13823242 (`r2lat`), 13823243 (`r2lat_hi`); closed loop 13823244-46 / 13823247-49 (L40S, after each); v8 controls 13822084-85 unchanged. Old ids 13822069-70 / 13822078-83 cancelled.
  - **Both trainings timed out (13823242-43, 1 h):** the node-local env build (garage2_env.sh, uv copy from the GPFS cache) took 2,533 / 3,198 s (7 min on Nov 5): the small-file slowdown again. **Fix:** `garage2_env.sh` now extracts a packed env `cache/g2env_v1_<pyproject md5>.tar` when present (checked by importing torch/py123d_garage/alpasim_grpc, else it builds); `cluster/pack_g2env.sbatch` (CPU, 13823446) builds once and packs. Requeued after it: training 13823447 (`r2lat`) / 13823448 (`r2lat_hi`), 2 h limit; closed loop 13823449-51 / 13823452-54; v8 control 13822085 now waits for the pack too. 13822084 started before the fix and is building the slow way.
  - **Pack fix works:** pack 13823446 built in 2,021 s, `cache/g2env_v1_a1d84585.tar` 7.4 GB (8.7 GB on disk); trainings extracted it in 142 s. v8 control 13822084 (slow build, 15 min compose) timed out at 1:15 before scoring; resubmitted as 13823589.
  - **Round 2 training (13823447 `r2lat` lr 2e-5, 13823448 `r2lat_hi` lr 1e-4; 15 min each):** 3,761 usable records (3,109 skipped), 666 scenes, train 3,354 / val 407 (73 scenes), 654 off-log. Labels are close to the model's own plans by design: before training, sampled L1 to the labels 0.789 m (round 1's log-timed labels: 2.914 m).
    - `r2lat`: loss 0.201 → 0.151 → 0.134 → 0.135 (50-step windows, by epoch); decoder moved 0.0005 relative L2; held-out cross-track 0.594 → 0.607 m (all), 1.402 → 1.382 m (off-log, n=72); L1 0.789 → 0.804. **Training loss fell but the held-out metric did not move: no offline gain at this dose.**
    - `r2lat_hi`: loss 0.183 → 0.129 → 0.112 → 0.109; moved 0.0010; held-out cross-track 0.594 → 0.571 m (-4%), off-log 1.402 → 1.222 m (-13%); L1 0.789 → 0.789 (all), 1.557 → 1.472 (off-log). **Modest offline gain, mostly on off-log states.** Validation n = 72 off-log records from 73 scenes, so treat the -13% as indicative only.
    - Closed loop on tuning (13823449-54) is what decides; both run, since offline gains have not predicted closed loop here.
- **Round 2 closed loop, tuning (300 scenes, start-now K=3, all L40S; baseline = v8 on L40S: controls 13823589 / 13822085 for s001/s010 + v8's own L40S s005 run):**
  - A/A: v8 L40S vs v8 original (H100 for s001/s010) -0.0009 [-0.0029, +0.0001], 280/300 identical, same 16 zeros. Noise is small.
  - `r2lat` (lr 2e-5): **-0.016 [-0.028, -0.006]**, W18 / L24, zeros 16 → 20 (4 new: 3 offroad, 1 at-fault collision; 0 fixed).
  - `r2lat_hi` (lr 1e-4): **-0.026 [-0.043, -0.010]**, W15 / L31, zeros 16 → 23 (8 new: 7 offroad, 1 at-fault; 1 fixed).
  - Round 1 on the same baseline: -0.0125 [-0.032, +0.006], 9 new zeros.
  - **Tested properly, no gain; both worse, CI below 0, and worse with more dose.** Lateral-only labels did not reduce offroads; they added them. Not adopted; held-out not spent.
  - **Open question:** is it the labels, or does any decoder-only fine-tune here damage driving? In both rounds the largest moved tensors were the flow-time / path-distance embeddings, not anything about geometry. **Control queued:** `r2self_hi` (13824491): same data, recipe and lr 1e-4, but the label is the policy's own served plan (perturbation removed), path loss weight 0; closed loop 13824492-94. If it also loses, the fine-tune recipe itself is the problem, not the labels.
- **2026-11-07, self-distillation control (`r2self_hi`, 13824491; closed loop 13824492-94, L40S):** same data, recipe and lr 1e-4 as `r2lat_hi`, label = the policy's own served plan, path loss weight 0.
  - **Validity:** loss_trajectory 0.079 → 0.057 → 0.050 → 0.047; decoder moved 0.0009 (largest again flow-time / path-distance embeddings); yet held-out L1 to its *own* plans rose 0.310 → 0.396 m and cross-track to the log path 0.594 → 0.632 m: training on its own outputs makes the sampled plans drift from them.
  - **Closed loop vs v8:** -0.003 [-0.018, +0.012], W13 / L34 (mostly small progress losses), zeros 16 → 15 (3 new, 4 fixed). So the fine-tune itself costs a little progress but does not add failures.
  - **`r2lat_hi` vs this control: -0.023 [-0.042, -0.004], 10 new zeros (8 offroad, 2 at-fault), 2 fixed.** The lateral labels themselves cause the extra offroads.
  - **Why (part 002, on-log moving records, n=156):** label minus the model's own plan, lateral (left +), at 1 / 2 / 4 s: straight -0.02 / -0.06 / -0.13 m, left turns -0.04 / -0.11 / -0.22, right turns -0.03 / -0.07 / +0.04, while the ego sits on the log (mean e +0.01). The labels pull the car ~0.1-0.2 m to the right of where the model drives even on straight road. Either the logged human drives right of the model's line, or the logged-trajectory reference point/frame differs slightly from the plan's (not resolved). Either way, imitating the log's lateral line is not what this simulator's drivable-area check rewards.
  - **Verdict: closed-loop decoder fine-tuning, tested properly in 3 label variants + control, no gain.** v8 stays the candidate. A debiased-label variant would mostly reduce to the self control (no gain), so I do not plan to pursue it.
- **2026-11-07, two rule tests (Aman: "run the two quick rule tests"):** both on top of v8 (start-now K=3), pre-specified single settings, tuning 001/010/005 + held-out 013/007/011 together, all L40S; paired vs v8 on L40S (controls 13823589 / 13822085, v8's own L40S runs for 005/007/011, new control 13825980 for 013, whose v8 run was on an L40). If positive, confirm on fresh scenes from the 7 CL-collection parts (rules don't train on them).
  - **(a) idx_start_penalty 19** (`EXTRA_OVERRIDES=controller.gains.idx_start_penalty=19`, a submission-time setting): alone on seed 0 it was tuning +0.012, held-out -0.010 (4 new zeros), but PCS-proxy positive. Jobs 13825968/70/72/74/76/78 (`g2k3idx19_*`).
  - **(b) Straight-road time warp 1.10** (`src/g2_cand/entry.py`, `G2_MODULE=g2_cand.entry`, `G2_TIME_SCALE=1.10`, heading change < 10° over 4 s): the organisers' GTRS-sample warp, ported to the 64-pose v0.2 plan (identical to our 8-point port at 0.5 s steps; poses after 4 s untouched), applied after start-now. On public py123d v0.1 it was +0.009 straight-only. `src/g2_addons/entry.py` stays byte-identical to the v8 image (md5 1252015d…). Jobs 13825969/71/73/75/77/79 (`g2k3tw110_*`).

### 2026-11-07 evening: rule tests, first shard
- L40S queue: 13 jobs pending ~4 h; VPN drop 11:26 to ~19:15. Only s001 done for both candidates; the rest are estimated to start 22:22 to 04:40.
- Activation: idx19 run's wizard command and config carry `controller.gains.idx_start_penalty: 19`; warp run logged "first warped plan" in 85 sessions (s001, 100 scenes).
- s001 only (100 tuning scenes) vs the v8 L40S control: idx19 +0.0072 [-0.012, +0.028] W6/L5, zeros 2→1 (1 offroad fixed); warp 1.10 -0.0038 [-0.019, +0.006] W6/L3, zeros 2→2. One shard, far from powered; no verdict.

### 2026-11-07 night: rule tests on top of v8, results
- **Validity:** all 13 jobs on L40S (ins038/039/063), all show start-now K=3; idx19 config carries `idx_start_penalty: 19`; warp logged "first warped plan" in 50-85 sessions per shard (most). Error-line counts equal the v8 runs' on the same shards (known foldback/corrupt scenes). A/A s013 v8 L40S vs L40: identical (0.0000, 100/100). Power: 561 paired scenes, 90% CI half-width ~0.007.
- **idx_start_penalty 19 + K=3** vs v8: tuning +0.0066 [-0.0001, +0.0143] W27/L8, 1 offroad fixed; **held-out -0.0124 [-0.0266, -0.0002]** W19/L12, 4 new zeros (2 offroad, 1 at-fault, 1 corridor); combined -0.0023 [-0.0097, +0.0045] W46/L20. The 4 new held-out zeros are **the same 4 scenes idx19 broke without start-now** (seed 0 and v8 score 1.0 on all 4): a deterministic idx19 failure, not noise.
- **Warp 1.10 straight-only + K=3** vs v8: tuning -0.0036 [-0.0131, +0.0049] W26/L6; held-out -0.0073 [-0.0198, +0.0028] W18/L9; combined -0.0053 [-0.0129, +0.0013], 5 new zeros (4 offroad, 1 at-fault; 2 shared with idx19). **Tested properly, no gain.**
- **PCS proxy refit** (same tool/commit as 11-04, 22 subjects incl. both candidates, 552 scenes, 3 fit seeds; `scratchpad/pcs/fit2_s{42,1,2}`), PCS minus v8 (g2sk3): k3idx19 +0.23 / +0.02 / +0.36; tw110 +0.24 / +0.02 / +0.11; posterior std ~0.2; seed 1 compressed again. Both proxy-positive but inside fit noise, and the population is ours only. Many small wins vs a few full zeros is exactly the mean/IRT split; the held-out zeros are on scenes every v0.2 variant passes, which the board's IRT (with stronger entries) is likely to punish.
- **Verdict:** warp: tested properly, no gain. idx19 on K=3: no gain shown (tuning gain does not hold on held-out; same 4 scenes break deterministically; proxy gain within noise). v8 unchanged. Fresh-part confirmation not run (pre-set condition was positive on both sets).

### 2026-11-08: v8 pushed (Aman)
- Pre-push checks (Mac, `local/n2:1`): entry.py md5 1252015d… = repo, `G2_START_K=3`, checkpoint sha256 d7113ef3… (released v0.2.0 posttrain seed 0), /opt/NOTICE present. No controller gains (defaults).
- `CLI limits`: 3 official left this month, nuplan-warmup 2 left; `v8` absent from the registry before the push.
- **`teams/amanupg:v8` pushed, digest sha256:5ea4001e7879bdb870784efd1e46c7e1879ebebbd87f13c482e9bad436cd5ab8** = local image id `5ea4001e7879` (the cluster-verified N2 image). Many layers already present (shared with earlier pushes).
- Open, Aman's call: HF checkpoint licence changed to CC BY-NC-SA 4.0 on 10-29; the image uses revision 56edbe90 (10-21, Apache-2.0 at the time), which NOTICE.n2 states.
- **v8 submitted to `nuplan` (Aman, 2026-11-08 20:00:33 UTC): submission `fcd5b9dd-52d6-4722-bb5c-24c6726f596e`**, image `teams/amanupg:v8` (digest 5ea4001e…), no controller gains. QUEUED 1/1. Monthly count 1 of 3 (2 left); the earlier attempt failed locally on an expired ECR login and used nothing. Throughput limit on nuplan is 3,000 s wall time (v6 used 1,189 s; v8 drops v6's judge, so expected lighter).
- Previous nuplan scores (board PCS-scale field): v6 1.766, v0.3-a15int8-1hz 1.278.
- **v8 official result (2026-11-08 21:06 UTC):** 1,000/1,000 rollouts valid, wall time 1,145 s of 3,000. Board (`CLI leaderboard --track nuplan`, saved to scratchpad lb_nuplan_1108.json): **PCS 1854 [1738, 1969], mean 0.9086, at-fault incident dist 0.682, dist to GT 0.836; entry rank 33 [25-38], team rank 18 of 58.** The status `score` field (0.836) is dist to GT, not PCS (v6's 1.766 likewise).
- **Board vs plain released model:** four teams submitted the released v0.2.0 joint64 seed 0 unchanged (team-gh gh-nuplan-v020-joint64-s0, terra-drive py123d-garage-ltfv6-j64s0, apex nuplan-ltf-s0-v1, my-drive-cosmos nuplan-v1): identical mean 0.9205, incident 0.834, dist to GT 0.669-0.671, **PCS 2074-2083**. v8 is that checkpoint + start-now K=3 and scores **-0.012 mean, -0.15 incident, +0.17 dist to GT, about -225 PCS** below it. Locally (552 scenes) the same pair went the other way: v8 vs seed 0 mean +0.012, dist to GT 0.696 vs 0.685. **Cause not established:** start-now misfiring on hidden-test scenes where waiting is right (fits the lower incident distance and higher dist to GT), or a difference between our image and theirs (driver v0.2.2 build, config). A warmup of `local/n:1` (same build, no start-now) would separate the two, if warmup results report metrics.

### 2026-11-09: candidate N3 = released joint64 posttrain seed 2 (Aman: "can we improve on the host's score even a tiny bit ... a small more promising gain is much better")
- **Warmups are not scored** (challenge README: smoke tests only), so the "warmup diagnostic" I suggested on 11-08 does not exist; board evidence costs an official slot (2 left).
- **Board sensitivity:** terra-drive j64s0-v2 vs v3 differ by 0.0003 in mean but 149 PCS (2081 vs 1932). Any change is a ±150 PCS gamble unless it breaks no scene strong entries pass.
- **Host per-scene results** (HF `v0.2.0/<model>/results/nuplan/seed_<n>`, 12 posttrain checkpoints x 1,485 public navtest scenes, e121e59, take-over 0.5 s): they reproduce ours (seed 0: 489/550 scenes identical, 3 zero flips). Mean vs joint64 seed 0 over 1,475 (10 foldbacks excluded): **joint64 seed 2 +0.0062 [-0.0015, +0.0139], W155/L88, zeros 15 new / 15 fixed**; every other checkpoint is worse (-0.007 to -0.024). Split: our 550 tuning/held-out +0.0001 [-0.013, +0.013]; the other 925 (never used by us) +0.0097 [-0.0000, +0.0196], W103/L46.
- **PCS proxy, host population (12 checkpoints x 1,475 scenes, 3 fit seeds; scratchpad pcsA):** seed 2 first in all fits, 3.93-3.97 vs seed 0 3.34-3.40 (std ~0.2). **Proxy validity check failed for start-now:** with host + our 9 variants on 550 scenes (pcsB), v8 (g2sk3) still ranks above seed 0 (+0.27, +0.29, +0.30), opposite of the board (-225). So the proxy, even with a strong population, cannot see the private-set failure of a situational rule; a whole-checkpoint swap is a different kind of change but is equally unconfirmed on the board.
- Selection caveat: seed 2 is the best of 12 on the same 1,475 scenes (winner's curse), and it breaks 15 scenes seed 0 passes.
- **Image `local/n3:1` built** (`container/Dockerfile.n3`, NOTICE.n3): FROM local/n:1, seed 0 removed, posttrain/model_2.pth (sha256 e450965d…, = HF @ 56edbe90), config identical (0fd09cd6…), entry and driver unchanged; checked inside: config points to model_2.pth, 844 tensors load. Id 31b8fd62e222. Not yet run on the cluster (VPN down).
- **Slot plan (Aman's call):** slot A = N3. If it beats ~2080, keep it as the final entry. If not, slot B = plain seed 0 (`local/n:1`), whose board result (~2080, four teams, deterministic) is known. Either way the team ends at >= ~2080.

## 2026-11-09 Seed 2 (N3): eligibility and realistic ceiling
- **Rules (challenge page, read today):** the leaderboard prize needs a final valid submission plus a technical report, and nuPlan award entries may use only public datasets, annotations and weights. Nothing in the page or the contestant guide (e121e59) requires a new method for the leaderboard prize; the innovation award is judged separately from the reports. Organisers may request method details from award candidates. Released seed 2 is public weights, so it is eligible as written; the report would have to say plainly that it is the host's released checkpoint, chosen using the host's published public-scene results.
- **Board 11-08, map from mean scene score to PCS (unchanged baselines and nearby entries):** 0.9205 → ~2080 (4 teams, plain seed 0), 0.9212 → 2088, 0.9242 → 2100, 0.9387 → 2141, 0.9405 → 2171. First place SymPhi 2198 (0.971). Seed 2's local edge (+0.006 to +0.010 mean) maps to roughly 2080-2110 if it carries over: top ~8-10, not a win and probably not top 3.
- **100-scene cluster check not run:** port 22 reachable but the login node closes the connection before auth ("Connection closed by 128.59.206.19x"), three attempts; stopped retrying.

## 2026-11-09 The host's rank-4 entry is a released checkpoint: waypoints seed 1 (candidate W1)
- Aman pointed at it; I had missed it. The host README for `ltf-base-waypoints-68M` (HF kesai-labs/py123d_garage_pretrained_checkpoints) says posttrain seed 1 is "the seed on the leaderboard" and lists nuPlan board scene 0.938, 0.981 km/at-fault incident, 0.590 m to GT. Host entry **093-nuplan-v1** (10-07): **PCS 2181 [2063, 2298]**, 0.9437 / **0.981** / **0.590**. Incident and GT distance match to 3 decimals (the scene score probably moved with the 10-22 corridor re-evaluation). Likewise joint32 README (seed 2: 0.919 / 0.678 / 0.627) = host 120-nuplan-v1 (1949, 0.9217 / 0.678 / 0.627).
- So a public, prize-eligible checkpoint has a board-measured PCS of ~2181 vs ~2080 for joint64 seed 0, even though it is **worse** than seed 0 on the host's own 1,485 local scenes. Local scores (and my PCS proxy) cannot rank released checkpoints; the board can. The seed 2 (N3) pick rested on local data and is superseded.
- Eligible standings 11-08: SymPhi 2198, Lucifer AI 2189, (host 2181), CQUPT 2171, 메타몽 2169, nuVAIL 2164. W1 at ~2181 would be about 3rd eligible, in final-run range; not first unless the refit moves things.
- **Image `local/w1:1`** (`container/Dockerfile.w1`, NOTICE.w1): FROM local/n:1, joint64 seed 0 + config removed, waypoints posttrain model_1.pth (sha256 ae1619d5…, = HF LFS oid) and its config.yaml (6a2f472d…) from HF @ 56edbe90; sensor rig unchanged (identical file). Checked inside (amd64 emulation): finalize_evaluation reads the waypoints config, TransfuserPolicy builds and loads **strict, 825 tensors, 67.1 M params**. Id/size: db5833d60444 36.1GB.
- Not verified: that our v0.2.2 driver reproduces the host's 10-07 image bit for bit. Planned check (needs the cluster): garage2 with this checkpoint on ~100 public scenes vs the host's published waypoints seed-1 per-scene results.

## 2026-11-10 New releases checked for nuPlan (Aman's LinkedIn finds)
- **Alpamayo 2 Edge** (nvidia/Alpamayo2-Edge, released 11-10, 2.45B + 0.2B action expert, weights OpenMDW-1.1): needs six NVIDIA cameras (front wide, front tele, cross L/R, rear L/R) with frames at -2, -1, -0.5, -0.1, 0 s; nuPlan delivers 8 Motional pinhole cameras at 0.5 s steps (no tele, no -0.1 s frames). Trained on ~115k h of NVIDIA driving. Same off-domain gap as Alpamayo 1.5 on nuPlan (board 1362 vs 2080 for py123d); OpenMDW vs the Apache-2.0 submission terms (§5) is also unresolved. Not usable in 6 days.
- **FlashDrive on Alpamayo 2 Super:** FlashDrive (z-lab) is a speed patch for Alpamayo 1/1.5; A2 Super is a 34B model it does not support. Speed does not raise the nuPlan score, and PAI is closed. No.
- **SimForge Pilot-4B v1.5** (Apache-2.0, gated: access needs accepting conditions): Qwen-Drive-1.0-4B + SimForge planning head; 3 x 120-degree f-theta NVIDIA cameras; reports 0.672 on 344 PAI NuRec val scenes (own runs); p95 drive latency 1.62 s on A100 (vs a 68M LTF). Off-rig for nuPlan, latency risks the 3,000 s budget, untested on nuPlan. No.
- v8 answer: no improvement; 1854 vs ~2080 for the same checkpoint unchanged.
- Cluster: port 22 timed out (VPN down), W1 harness check still pending.

## 2026-11-10 W1 verified; failure analysis; 3-seed waypoints ensemble test
- **W1 harness check (13852543, 13852545; garage2 = py123d v0.2.2 natively, waypoints posttrain model_1.pth sha ae1619d5…, L40S):** vs the host's published W1 per-scene results (HF `results/nuplan/seed_1`, run name `093_v0_2_0_eval_alpasim_nuplan_route_off_seed1`), shards 001 + 013, 200 scenes: **182 identical, mean 0.9044 vs 0.9044, diff -0.0000 [-0.0001, +0.0000], no zero-score flips.** Our driver reproduces the host's 093 run; with the board deterministic, `local/w1:1` should score ~2181 (modulo refit drift). Infra: nodes ins038, ins057, ins059, ins061 (exit 0:53 in 1-2 s, no log) and ins063 (CUDA unknown error) failed jobs; now excluded.
- **Videos** (13852564, VIDEO=true, 15 W1 failure scenes): all 15 reproduce the host's scores (14 exact). Clips in `analysis/w1_videos/`, frame grids `analysis/w1_*.jpg`, list of all 241 losing scenes in `analysis/w1_failures_public1485.csv`.
- **Where W1 loses (host data, 1,485 public scenes, mean 0.902):** low progress 179 scenes, 58 % of lost score (63 scenes < 2 m driven; GT only 9.4 m median there, i.e. starts from rest; 24 of the 63 rear-ended by log-replayed followers); offroad 53 (36 %; median 14 m driven of 31 m; 34 of 53 driven clean by another released checkpoint); at-fault collision 8; corridor 1. Videos: waits at a red light the human drove through (light looks red in every rendered frame; frozen reconstructed light suspected, not verified), never moves on an empty street, stays behind a stopped car, drifts onto a median curb.
- **Scene facts (e121e59 configs):** 4 s scored after a 0.5 s log replay, decisions every 0.5 s; score 0 on at-fault collision / offroad / lateral corridor exit, else min(1, progress / 0.8), full if GT < 5 m; progress stops once > 4 m from the GT path or at any collision; trafficsim skipped (other agents replay the log). Eval container: no outbound network, 16 GiB VRAM per driver, 0.1 s/Drive target, 3,000 s budget.
- **3-seed waypoints ensemble (posttrain model_0+1+2, plans averaged), shards 001 + 013 (13852544, 13852563) vs our W1:** +0.0093 [-0.0012, +0.0231], 176/200 identical, W11 / L13, **no new zero-score scenes** (none fixed). Per shard: 001 +0.002, 013 +0.016. Drive call 0.136 s vs 0.050 s (L40S). Widening to 005/007/010/011 (13853199-200, 13853277-78). Caveat: the joint64 3-seed ensemble was tuning +0.007, held-out -0.019; and local gains have not transferred to the board (v6, v8).
- **3-seed waypoints ensemble, all 6 shards (557 scenes paired with W1; our W1 runs where available, else the host's published W1, which ours reproduces):** **+0.0074 [-0.0047, +0.0202], 475 identical, W34 / L48, 4 new zero-score scenes, 3 fixed.** Per shard: 001 +0.002, 013 +0.016, 005 -0.012, 007 -0.012, 010 +0.034, 011 +0.009; signs flip across shards. Validity: same GPU type (L40S), same scenes, reference reproduced. **Verdict: no gain shown (underpowered; mean up, but more scenes lost than won and failures traded, not removed).** Same shape as the joint64 3-seed ensemble (tuning +0.007, held-out -0.019).

## 2026-11-10 Shadow mode for the two candidate fixes (W1, 552 nuPlan scenes)
- **Shadow driver** `src/g2_shadow/entry.py` (wraps TransfuserPolicy.forward and GarageDriver._plan; plans unchanged, verified on the 3-scene smoke: scores = plain W1). Logs per plan: speed, 64 poses, route ahead (rig frame), the model's own boxes (class, speed, heading), predicted drivable probability at each pose and 1 m to each side; argmax BEV per plan. Runs 13854243-48 (6 shards, 552 scenes with logs; outcomes clean 469, low 38, stuck 23, offroad 17, collision 3, corridor 2). Analysis `src/analysis/shadow_triggers.py`.
- **Fix 2 (off-road guard from the predicted road): not viable.** Best settings catch 2-3 of 17 off-road scenes with 0-2 clean firings (H=2 s, P<0.1 at a side sample: 2/17 offroad, 0/469 clean; P<0.3: 3/17, 15 clean). The predicted map is sensible (Boston median scene, `analysis/w1_predicted_bev_boston_offroad.png`: both roadways, median, walkways, centre lines, cars) but the failure is a sub-metre drift onto the curb that the map does not resolve: the plan's own poses read 0.97-1.0 drivable at the centre and 0.72-0.89 at 1 m to the side while it drives off-road. Dropped.
- **Fix 1 (stall nudge) trigger is selective.** Slow (< 0.5 m/s), plan moves < 1 m in 2 s, no box of any class within 25 m along the route corridor (|lat| < 2 m), no crossing moving vehicle/two-wheeler within 30 m, no static object (sign/barrier/cone) within 15 m ahead / 8 m lateral, holding for **K = 3 consecutive plans**: fires in **18/23 stuck, 7/38 low, 4/469 clean, 0 failing** scenes (K=1: 28 clean; K=2: 17 clean). On the same logs **v8's start-now trigger (K=3) fires in 11/23 stuck and 27/469 clean**: the box conditions remove most of start-now's clean firings and catch more stalls. Of the 4 clean firings, 2 are scenes where the human moved < 5 m (full score anyway, so only risk). Firing comes at plan 2 (1.5 s into the 4 s window) in most stuck scenes.
- **Plan shapes at firing:** 9 stuck scenes are wait-then-go (the plan itself moves 4-23 m by 6.4 s; nudge = drop the wait, as start-now), 9 are stay-stopped (plan ~0 m throughout; a nudge must make motion along the route, riskier). Of the clean firings, 3 are wait-then-go, 1 stay-stopped.
- NuRec: renderer image job 13853832 hit OOM at 16 GB (chain cancelled); resubmitted with 96 GB (13854931), smoke 13854932, full j64s0 + v8 13854933-44 depend on it and on the scene fetch (208/441 at 19:xx).

## 2026-11-10 Fix 1 built (stall nudge, versions A and B); corridor bug in the shadow trigger fixed
- **Bug found while building:** the driver's route (`session.route_xy_local`) often starts ~40 m ahead of the ego (the driver walks its target points from the ego onto it). The shadow trigger measured boxes against that route alone, so a box between the ego and the route start could read as far off the corridor. Fixed in `shadow_triggers.corridor_lateral` and the nudge: the path is ego + route. **Corrected counts (K=3, D 25, C 2): stuck 14/23, low 4/38, clean 1/469, failing 0** (K=1: 16 clean; K=2: 11 clean). The earlier 18/23 and 4/469 figures are superseded.
- **`src/g2_nudge/entry.py`** (G2_NUDGE_MODE): trigger as above, acts after 3 firing plans in a row, then latched (acts on any single firing plan). **A:** wait-then-go plans only, drop the waiting prefix (v8 start-now action). **B:** A, plus for stay-stopped plans a gentle start along ego->route (1.0 m/s^2 up to 4 m/s), only if that path heads within 20 deg of straight over its first 10 m (no creeping into turns). Offline check on the shadow logs: trigger agrees with the analysis on all 5,520 plans; B creep fires in 4 stuck scenes and 1 clean (32d85d…, human moved 4.6 m, so full score at risk).
- Runs: A 13856052-57, B 13856058-63 (same 6 shards; baseline = the shadow runs 13854243-48, plans unchanged). `src/analysis/paired_compare.py` for the paired comparison.
- L40S runs never started (the 3 L40S nodes not on the exclude list were full); cancelled 13856052-63. Moved to **A6000** with a matching plain-W1 baseline on A6000 (paired on the same GPU type): baseline 13856776-81 (`w1a6k_s*`), A 13856782-87, B 13856788-93.
- **A6000 was a mistake:** the nuPlan MTGS renderer is built for sm 8.9/9.0 only (L40S/L40/H100; noted in sim_nuplan.sbatch), and A6000 CPUs were fully allocated anyway. Cancelled 13856776-93 (never started). L40S resubmit 13857125-36 cancelled too: the 3 usable L40S nodes are held by other users' 11 h / 2-day jobs.
- **Firing-set design instead of full shards:** until the nudge first acts, a scene drives bit for bit as plain W1 (the trigger only reads the model's outputs), so the trigger sees what shadow mode saw and scenes where it never fires cannot change. So only scenes where the trigger fires at all (K=1, any plan, corrected corridor; superset of the K=3 set to absorb GPU-type drift): **40 scenes** (16 stuck, 16 clean, 8 low), `analysis/nudge_fireset40_scene_ids.txt`. Run plain W1, A and B on them on **H100** (paired on one GPU type): 13857138 (base), 13857139 (A), 13857140 (B). Pooled effect over all 552 = (sum of differences on the 40) / 552. Caveat: a scene that would fire on H100 but never on L40S is not covered.
- The separate H100 jobs were queued one after another (est. starts 00:00 / 02:35 / 03:50; the one free H100 had only 16 GB of host memory left, our runs peak at ~17.6 GB). Replaced by **one job running base, A and B in sequence on the same GPU** (`cluster/sim_nuplan_multi.sbatch`, any of L40S/L40/H100, pairing kept inside the job): **13857369** (TAG w1f40_0/A/B), est. start 00:00. Cancelled 13857138-40.
- **NuRec image job 13854931 ran out its 6 h** in apptainer's unpack/mksquashfs with the temp dir on the dept fileset (millions of small files on GPFS). Cancelled it with its chain. Now: pull on the node's /local and copy only the .sif to `$B/sif` (`nurec_fetch.sbatch` PART=image, 16 cores, 64 GB, 3 h); each NuRec job unpacks the .sif to a sandbox on its own /local (`sim_nurec.sbatch`). Resubmitted: image 13857971, smoke 13857972, j64s0/v8 x 6 chunks 13857973-84. Leftover from the timed-out build: `tmp/apptainer/build-temp-2776908158` on the fileset (size not measured, `du` timed out) - delete only with Aman's OK.
- Socket dropped ~00:30; reopened (key auth). Paired job 13857369 started 00:06 on ins048 (H100).
- Aman OK'd deleting `tmp/apptainer/build-temp-2776908158` (contained only rootfs/ from the timed-out build); deleting via CPU job 13858033 (not on the login node). `bundle-temp-1756160721` (18 KB) left in place.

## 2026-11-11 Stall nudge on its 40 trigger scenes (tuning set): A +0.0129, B +0.0164 over 552, no losses
- **Job 13857369 (ins048, H100), plain W1 / A / B in sequence on the 40 scenes where the trigger ever fires** (firing-set design above). Validity: all three runtime exit 0; H100 base vs the L40S shadow runs on the same 40 scenes: 27 identical, the rest differ in the third decimal (GPU type); the trigger reached K=3 in exactly the 19 scenes shadow mode predicted (14 stuck, 4 low, 1 clean).
- **A (drop the wait): +0.178 [+0.082, +0.286] on the 40, W11 / L0, no new zeros; acted in 11 scenes.** Pooled over all 552 (other scenes identical by construction): **+0.0129**.
- **B (A + creep along ego->route for stay-stopped plans): +0.226 [+0.120, +0.340] on the 40, W14 / L0, no new zeros; acted in 15 (4 creeps in stuck scenes: 0 -> 0.68, 0 -> 1.0, 0 -> 0.29, 0 -> 0.13; the one clean creep scene 32d85d… stayed 1.0).** Pooled over 552: **+0.0164**.
- Verdict: **gain shown on the tuning set only** (the trigger was designed on these scenes). Not yet confirmed on held-out.
- **Why held-out alone is not enough:** v8's start-now (same action as A) gained locally on tuning, held-out and fresh, then lost on the board: incident distance 0.834 -> 0.682 km (more at-fault incidents per km), dist to GT +0.17, ~-225 PCS. So the nudge also goes to NuRec, where the v8-vs-j64s0 pair tests whether NuRec catches what local nuPlan missed.
- **Submitted:** nuPlan fresh parts 002/004/006/008/009/012 (scenes outside the 568 local ones; never used for the nudge design), base/A/B in one job each on one GPU: 13858151-56. NuRec W1 base (`w1`) and B (`w1nudgeB`), 6 chunks each, R6000, after the smoke 13857972: 13858139-50 (A on NuRec later, only on the scenes where B's trigger reached K; elsewhere A = B = base by construction).
- **NuRec smoke 13857972 failed in 3 min, image fine:** `data/nurec_curated_val_ids.txt` has CRLF line endings, so every id carried a `\r` and the wizard found no scene. Fixed in `sim_nurec.sbatch` (`tr -d '\r'`, skip empty lines; chunk 0 of 6 = 73 clean ids). The dependent chains had been cancelled by Slurm. Resubmitted: smoke 13858404; then per chunk c=0..5, j64s0 / v8 / w1 / w1nudgeB = 13858405-28 (4 per chunk in that order).
- **Smoke 13858404 failed at the NRE unpack** (ids now accepted, compose generated): apptainer needs `APPTAINER_TMPDIR` to exist. Added `mkdir -p`. Resubmitted: smoke 13858436; j64s0 / v8 / w1 / w1nudgeB per chunk 0..5 = 13858437-60.
- **Smoke 13858436: NRE unpacked fine on /local; compose stopped** because the bind target `.../libs/nrend/ptx_cache` (NRE's kernel cache, bound to `cache/containers`) does not exist in a fresh unpack (the old GPFS sandbox had it from earlier runs). The per-job sandbox is ours, so the job now creates it and records the runtime layout in `$RUN/nre_layout.txt`. Resubmitted: smoke 13858479; j64s0 / v8 / w1 / w1nudgeB per chunk 0..5 = 13858480-503.
- **NuRec smoke 13858479 passed** (R6000 ins046, 10:50 with unpack; 2 scenes, runtime exit 0, scores 0.689 / 0.675, no incidents, driver peak 1.2 GB). **About 4 min per scene**, so a 73-scene chunk (~4.9 h) would hit the 5 h limit, and only ins046 has R6000s (8, shared; ins047 draining). 4 drivers x 441 scenes = ~118 GPU-h: too slow for the deadline.
- **Switched NuRec to the firing-set design:** plain W1 and plain joint64 s0 once each on all 441 with shadow logging (plans unchanged), 12 chunks of ~37, 3.5 h limit: w1sh / j64s0sh per chunk 0..11 = 13858689-712 (w even, j odd). Cancelled the 24 full-chain jobs (13858480 had just started). Then B and v8 run only on their firing scenes, paired with a base rerun in the same job.
- `src/analysis/firing_sets.py`: exact and loose firing sets from shadow logs for the nudge (exact = run >= K, loose = any firing plan) and v8 start-now (exact = run >= K+1 of stopped wait-then-go plans, loose >= K-1). Check on the nuPlan shadow logs: nudge exact 19 (14 stuck, 4 low, 1 clean) = the live run; loose 40 = the tuning set. Start-now exact 28 (11 stuck, 8 low, 9 clean), loose 75.
- Delete job 13858033 hit its 2 h limit about halfway (single-thread rm on GPFS); resubmitted with 8 parallel rm, 5 h: 13858519.
- **Fresh nuPlan part 002 (13858151, H100 ins048; 100 scenes never used for the nudge design):** validity: 0 / A / B all exit 0; 96 of 100 scenes identical across variants. **A = B: +0.0221 [+0.0026, +0.0476], W4 / L0, no new zeros** (2 stuck 0.14 -> 0.70, 0.10 -> 1.0; 2 low 0.74 -> 1.0, 0.48 -> 0.97; all drop_wait, B's creep never acted). One part of six; pooled verdict after the rest.
- **Fresh part 004 (13858152):** all exit 0. **A = B: +0.0179 [+0.0000, +0.0446], W3 / L0, no new zeros** (stuck 0.00 -> 1.0; low 0.58 -> 0.82, 0.44 -> 1.0; drop_wait only). Running total over 200 fresh scenes: W7 / L0.
- Delete job 13858519 finished: `tmp/apptainer/build-temp-2776908158` is gone; `bundle-temp-1756160721` (18 KB, not approved) left in place.
- **Fresh part 006 (13858153):** all exit 0. **A = B: +0.0208 [+0.0018, +0.0480], W5 / L0, no new zeros** (2 stuck 0.05 -> 0.67, 0.00 -> 1.0; 3 low). Running total over 300 fresh scenes: W12 / L0; B's creep has not acted on any fresh scene yet.
- **Fresh part 008 (13858154):** all exit 0. **A: no change (W0 / L0). B: +0.0098 [+0.0000, +0.0286], W2 / L0, no new zeros**, both through creep (stuck 0.13 -> 0.22, 0.00 -> 0.90; 4 creep plans logged), the first creeps on fresh scenes. Running total over 400 fresh scenes: A W12 / L0, B W14 / L0.
- **NuRec base chunk 0 (w1sh 13858689, j64s0sh 13858690; R6000 ins046):** both runtime exit 0, 36/36 scenes, ~1 h 50 min (~3 min/scene), shadow logs for all 36. W1 0.707 (passed 30/36), j64s0 0.725 (32/36).
- **Triggers fire far more on NuRec:** chunk 0, nudge exact 9/36 on W1 (vs 19/552 on nuPlan), start-now exact 10/36 on j64s0. Start speeds match (stopped at start: 17% NuRec vs 16% nuPlan) but NuRec scenes are ~20 s (40 plans) vs ~5 s, with more mid-scene stops (18% of plans stopped vs 9%). So NuRec gives the nudge many more chances to misfire (e.g. at red lights, which the trigger cannot see): a harder check, which is what is needed after v8. Nudge firing scenes on W1 include 2 off-road failures.
- **Chunk 0 candidate runs on the loose firing sets** (`runs/nurec_sets/`): nudge set (14 scenes) W1 rerun / A / B = 13858961-63; start-now set (16) j64s0 rerun / v8 = 13858964-65. The reruns measure NuRec run-to-run repeatability; if exact, later chunks skip them.
- **Fresh part 009 (13858155):** all exit 0. **A = B: +0.0100 [+0.0000, +0.0299], W1 / L0** (stuck 0.00 -> 1.0); B logged 2 creep plans with no score change. Running total over 500 fresh scenes: A W13 / L0, B W15 / L0.
- **Fresh part 012 (13858156):** all exit 0. A = B: +0.0001, W1 / L0 (0.995 -> 1.0).
- **Pooled over the 6 fresh parts (600 scenes, never used for the design; base/A/B paired on one GPU per part; all 18 runs exit 0; unchanged scenes identical across variants):**
  - **A: +0.0118 [+0.0051, +0.0198], W14 / L0, no new zeros** (6 stuck, 8 low).
  - **B: +0.0134 [+0.0063, +0.0220], W16 / L0, no new zeros** (B = A + 2 creep wins in one part).
  - Verdict: **gain confirmed on held-out nuPlan** for both. Same size as the tuning-set estimate (A +0.013, B +0.016). Caveat that keeps this from being a submit decision: v8 also gained about +0.012 on local held-out nuPlan and then lost ~225 PCS on the board. Unlike v8, the nudge has 0 losses in 600 fresh scenes, but local nuPlan did not show v8's failure mode either. NuRec (longer scenes, many more firing chances) is the remaining check.

## 2026-11-11 NuRec chunk 0: B's creep makes 2 new zeros; A clean; NuRec not bit-repeatable
- Base chunks: 20 of 24 done by ~16:00 (ins047 came back, so throughput ~8 GPUs, not ~3). All valid (runtime exit 0, every scene scored, shadow log per scene). w1sh c11 13858711 failed in 2 min: scene `clipgt-76f7e025-…` was never fetched (440 / 441 local). Dropped it: c11 rerun for both models on 35 scenes (`runs/nurec_sets/c11_minus1.txt`): 13863848 (w1), 13863849 (j64s0); cancelled 13858712.
- **NuRec is not bit-repeatable:** W1 rerun vs original on the 14 chunk-0 nudge scenes: -0.0016 [-0.0056, +0.0012], 8 of 14 scenes differ in the 2nd-3rd decimal (one 1.0 -> 0.977). So candidates are always paired with a base rerun.
- **Chunk 0 nudge set (14 scenes), vs the W1 rerun:** **A +0.0364 [+0.0009, +0.1027], W5 / L3 (losses <= 0.004), no new zeros** (stuck 0 -> 0.46). **B -0.0924 [-0.311, +0.092], W7 / L4, 2 new zeros:** both clean scenes where W1 stops mid-scene (plan 29 and 14 of 40; likely a light or stop line the trigger cannot see), waits, then goes; B creeps during the wait: one corridor exit, one at-fault collision. Local nuPlan scenes (~5 s) only fire near the start, so this never showed there.
- **New variant Bs (`G2_NUDGE_CREEP_FROM_REST=1`):** creep only while the ego has not yet reached 0.5 m/s in the session (all creep wins on nuPlan were cars that never got moving). Offline replay on the shadow logs: Bs does not creep in either NuRec failure scene and keeps the creeps in the nuPlan tuning stuck scenes.
- **Firing sets, NuRec chunks 1-9 (333 scenes):** nudge on W1 exact 96 / loose 127 (loose: 77 low, 28 clean, 4 stuck, 18 failing); start-now on j64s0 exact 101 / loose 142. Loose sets split round-robin into 4 groups (`runs/nurec_sets/*_g00..03`, 31-36 scenes). Submitted per group g: W1 rerun / A / Bs and j64s0 rerun / v8: fsg0 13863860-64, fsg1 65-69, fsg2 70-74, fsg3 75-79 (order re, A, Bs, j64re, v8). Bs on the chunk-0 nudge set: 13863859. Plain B dropped (2 new zeros in chunk 0; Bs replaces it). Chunk-0 v8 pair 13858964-65 still running.
- **Chunk 0 start-now set (16 scenes): v8 vs j64s0 rerun -0.0245 [-0.185, +0.107], W5 / L4, 1 new zero (at-fault collision, `clipgt-8a365ac2`, j64s0 1.0).** j64s0 rerun vs original +0.0001 [-0.0048, +0.0043]. Direction matches v8's board result (more at-fault incidents); one chunk only. Same scene under W1: plain W1 never moves (0), A starts it without a collision (0.46).
- **Chunk 0 nudge set: Bs vs W1 rerun +0.0443 [+0.0013, +0.1231], W5 / L4 (losses <= 0.008), no new zeros, no creep fired**; both scenes B broke stay 1.0.
- **ins046 node fault 17:46:20-17:46:44:** all our running jobs there died (exit 120, mid-render, no error in any service log) and every job started there in that window died at launch (exit 0:53, no log); the jepa-nureasoning thread's job on ins046 died the same way, and its notes record the same 0:53 launch kills on ins087-091. Jobs started there after 17:48 run normally. Not our code. Resubmitted unchanged: j64s0sh c11 13864490; fsg1 re/A/Bs/v8 13864491-94 (fsg1 j64re 13863868 survived on ins047); fsg2 13864495-99; fsg3 13864500-04. Base chunk 10 for both models done (13858709-10).

## 2026-11-11 NuRec group 0: A clean again; Bs's creep causes an at-fault collision; Bs dropped
- **Group 0 (chunks 1-9 loose set, round-robin part 0), all 5 runs exit 0 (13863860-64).** Scenes the add-on never touched are identical between candidate and rerun in this group.
- **A vs W1 rerun (32 scenes): +0.0341 [+0.0017, +0.0757], W7 / L0, no new zeros** (low 0.63 -> 1.0, 0.12 -> 0.59, 0.41 -> 0.62, four small gains).
- **Bs vs W1 rerun (32 scenes): +0.0341 [-0.061, +0.127], W8 / L1, 1 new zero, 1 fixed zero.** Same seven wins as A plus two creep scenes:
  - `clipgt-81dc4ece`: W1 and A 1.0 (wait, then go, 23.6 m). Bs creeps from rest at plans 6-7 and hits the vehicle ahead: **at-fault front collision at ~6 s, score 0**. The box gate saw nothing in the corridor, so the model's boxes missed this obstacle.
  - `clipgt-d5e79abb`: W1 and A off-road 0. Bs creeps from rest at plans 2-4, finishes clean, 1.0.
  - Net 0 but it trades a fixed off-road for an **at-fault collision, the incident type v8 added on the board**. Creep-from-rest does not make the creep safe on NuRec. **Bs dropped**; cancelled pending fsg3 Bs 13864502 (fsg1/fsg2 Bs, already >1 h in, left to finish for the record).
- **v8 vs j64s0 rerun, group 0 (36 scenes): +0.0050 [+0.0010, +0.0112], W10 / L0, no new zeros.** Chunk 0 was -0.0245 with one at-fault collision; pooled verdict after all groups.
- Chunks 10-11 base done (w1 c11 13863848 exit 0, 35 scenes; j64 c11 13864490 still running). Firing sets: nudge on W1 c10+c11 exact 12 / loose 26; start-now on j64 c10 exact 7 / loose 11. Submitted fsg4: W1 rerun / A = 13865175-76 on the 26; j64s0 rerun / v8 = 13865177-78 on the 11.

## 2026-11-11 NuRec groups 1-2: A clean; its losses are rerun noise
- All runs exit 0: fsg1 re / A / Bs / j64re / v8 = 13864491 / 92 / 93 / 13863868 / 13864494; fsg2 re / A / Bs = 13864495-97. j64s0sh c11 13864490 exit 0 (35 scenes).
- **A vs W1 rerun:** g1 +0.0276 [+0.0005, +0.0739], W12 / L5, no new zeros, 1 fixed zero (collision 0 -> 0.65). g2 +0.0365 [-0.0045, +0.1068], W12 / L5, no new zeros (stuck 0.00 -> 1.0). Every loss is progress only (no collision, off-road or corridor exit). The biggest (-0.109, `clipgt-c028c8ce`) is a scene where A never acted.
- **Bs vs W1 rerun:** g1 +0.0261, W9 / L9; g2 +0.0361, W11 / L6; no new zeros, no creep wins. Nothing over A; stays dropped (group 0 collision).
- **A pooled over chunk 0 + groups 0-2 (110 firing-set scenes), split by whether A acted** (nudge log has a non-`none` action):
  - **acted (54 scenes): +0.0674 [+0.0245, +0.1230], W27 / L2, worst -0.062, no new zeros.**
  - never acted (56): +0.0002 [-0.0060, +0.0070], W9 / L11, worst -0.110. That is NuRec rerun noise (the scene drives as the base until the add-on acts), so the scene-level losses seen per group are mostly noise.
- **v8 vs j64s0 rerun, g1 (36 scenes): +0.0131 [+0.0007, +0.0287], W16 / L7, no new zeros** (one clean 1.0 -> 0.914). v8 pooled so far: chunk 0 -0.0245 (1 at-fault collision), g0 +0.0050, g1 +0.0131.
- Firing set start-now on j64 c11: exact 11 / loose 19; submitted fsg5 j64re / v8 = 13865320-21.

## 2026-11-11 NuRec complete for A: at-fault collisions after A acts; A not clean
- All runs exit 0: fsg3 re / A = 13864500-01 (31 scenes), fsg4 re / A = 13865175-76 (26, chunks 10-11). Aman: K=2 not to be tested ("k=2 seems kinda pointless"); GPU-count cap lifted through the deadline.
- **fsg3 A vs W1 rerun: -0.0025 [-0.138, +0.133], W14 / L9, 3 new zeros, 2 fixed. fsg4: -0.0352 [-0.116, +0.009], W5 / L7, 1 new zero.**
- New zeros, inspected:
  - `clipgt-229791a5` (fsg3, clean 1.0): A drop_wait at plan 14, **at-fault front collision ~2 s later**. Caused by A.
  - `clipgt-58814d76` (fsg4, clean 1.0): A drop_wait at plan 9 after 8 stopped plans, **at-fault front collision ~2 s later**. Caused by A.
  - `clipgt-0b54c8d4` (at-fault collision) and `clipgt-a5599793` (off-road, at ~7 s): A never acted. NuRec rerun noise.
- **Pooled, all 167 firing-set scenes (chunks 0-11):**
  - acted (79): +0.0461 [-0.0117, +0.1041], W39 / L8; new zeros 2, fixed zeros 2; new at-fault collisions 3, removed 1.
  - never acted (88, = noise): -0.0112 [-0.045, +0.018]; new zeros 2, fixed 1; new at-fault 1, removed 0.
  - over all 440 NuRec scenes: +0.0060 per scene (all changes) / +0.0083 (acted only).
- Validity: every run exit 0 and fully scored; paired reruns on the same scenes and GPU type; firing sets from the base pass. Power: weak for incidents, since rerun noise alone made 2 new zeros in 88 scenes.
- **Verdict: no gain shown on NuRec (CI includes 0), and A adds at-fault front collisions after it acts (3 vs 1 in the noise half; both clean-scene ones ~2 s after drop_wait).** This is v8's board failure mode at a lower rate. Not a safe candidate as is.
- Fresh nuPlan part 015 (W1 0 / A) running: 13865497 (L40S ins036).

## 2026-11-11 Aman: submit A ("go out on a limb"); image local/w1n:1 built
- Aman's call after the NuRec read: submit W1 + nudge A rather than plain W1. Board order is by team best entry (PAI board, LEDGER alpasim), so with 2 slots plain W1 (`local/w1:1`, ~2181) stays available as the fallback if A scores lower.
- **Image `local/w1n:1`** (`container/Dockerfile.w1n`, `NOTICE.w1n`): FROM `local/w1:1` + `/opt/addons/g2_nudge`, `ENV PYTHONPATH=/opt/addons G2_NUDGE_MODE=A G2_NUDGE_K=3`, ENTRYPOINT `python -m g2_nudge.entry` (same config string as W1). Checked inside: entry.py md5 93677e79… = repo = cluster copy used for the NuRec runs; model_1.pth sha256 ae1619d5…, config.yaml 6a2f472d…; install() patches TransfuserPolicy.forward and GarageDriver._plan; MODE A, K 3, latch on, creep-from-rest off, no log dir. Id sha256:da1fe936…, 12.8 GB. Not pushed. Tag: v9 (next neutral tag) unless the registry says otherwise.
- Next: archive to the cluster, imagep run on fresh parts paired against the garage2 A runs (same check as v8's image).

## 2026-11-11 NuRec complete for v8; NuRec vs board calibration
- fsg3 v8 / j64re (13864504 / 13864503) exit 0, 35 scenes: -0.0036. fsg5 (chunk 11, 19): +0.0076. fsg4 (chunk 10, 11): -0.0322.
- **v8 vs j64s0 rerun, all 188 start-now firing scenes: -0.0009 [-0.024, +0.019], W62 / L21, 4 new zeros (3 at-fault collisions on scenes j64s0 scores 1.0: `8a365ac2`, `de9db5dc`, `b44a4a44`; 1 off-road), 0 fixed zeros; at-fault collisions +3 / -0.** Over all 440 scenes -0.0004 per scene.
- **Same totals for A (167 scenes, acted and noise together): +0.0159 mean, new zeros 4 / fixed 3, at-fault collisions +4 / -1.** A has a better mean and fixes zeros v8 never fixes; new incidents about the same as v8.
- **Calibration against the board (two known pairs):**
  - W1 vs j64s0: board W1 better (0.944 vs 0.921; 0.981 vs 0.834 km/incident). Local nuPlan said j64s0 better (wrong). NuRec base pass (440): W1 0.685 vs 0.668 (right), km/incident 1.088 vs 1.096 (tie).
  - v8 vs j64s0: board v8 worse (-0.012, more incidents). Local nuPlan +0.012 (wrong). NuRec: flat mean, +3 at-fault collisions, 0 fixed (right on incidents).
  - Incident rates: W1 km per at-fault incident (offroad or at-fault collision): board 0.981, local nuPlan fresh 1.195 (600), NuRec 1.088 (440); mean score board 0.944, nuPlan 0.920, NuRec 0.685. Board scenes look like nuPlan in difficulty; NuRec has been the better guide to add-on direction (2 of 2, weak).
- Read for A: NuRec profile close to v8's on incidents, better on mean; best guess A below W1 on the board, low confidence; no PCS estimate (board PCS moves 149 for 0.0003 of mean in the terra-drive pair). Aman's call stands: warmup first, then submit; W1 (`local/w1:1`) remains the fallback slot.
- Archive `tmp/w1n.tar.gz` on the cluster (12.8 GB, sha256 f2af2367… = Mac copy; Mac copy deleted). Image check (imagep from the archive, IMAGE_MODULE=g2_nudge.entry, same GPU type as the tested garage2 A run of each part): fresh part 002 on H100 13866187, part 004 on L40 13866188. Pass = scores match the garage2 A runs (13858151 / 13858152) scene for scene, driver.log shows `mode=A K=3`.
- Aman (11-11 night): "we anyways have nothing so might as well just submit A"; last slot kept for W1. Warmup first (Aman pushes `v9` and submits the warmup), official after the image check.

## 2026-11-12 v9 image check passed; fresh part 015 A vs W1
- **Image check (imagep from `tmp/w1n.tar.gz`, IMAGE_MODULE=g2_nudge.entry): passed.** Part 002 (H100, 13866187) vs garage2 A 13858151: 100/100 scenes identical (diff +0.0000, W0/L0). Part 004 (L40, 13866188) vs garage2 A 13858152: 100/100 identical. driver.log in both: `g2 nudge: mode=A K=3 V=0.50 acc=1.0 vmax=4.0 latch=1 creep_from_rest=0 log=-`. Checkpoint inside the image: model_1.pth ae1619d5…, config.yaml 6a2f472d… (= W1). Against W1 0 on the same parts: 002 +0.0221 W4/L0, 004 +0.0179 W3/L0 (the same A wins as before).
- Validity: both exit 0, all scenes scored, same scene lists and GPU types as the reference runs. So `local/w1n:1` drives exactly as the A we tested; a packaging slip is ruled out. It says nothing new about A vs W1 on the board.
- **Fresh part 015 (L40S ins036, 13865497), W1 0 vs A, 91 scenes both arms, exit 0: +0.0231 [+0.000, +0.054], W3/L0, new zeros 0, fixed 0.** All three wins are stuck scenes (0.339→0.741, 0.300→1.000, 0.004→1.000). Consistent with earlier fresh nuPlan parts: A helps on nuPlan with no losses; NuRec is where A's collisions show up, and NuRec has been the better guide to the board (2 of 2, weak).
- Cluster archive `tmp/w1n.tar.gz` deleted after the check (own temp file).

## 2026-11-12 Rule: final runs use the team's highest-scoring submission
- NVlabs/alpasim#232 (asked for PAI, 2026-10-31; organiser mwatson-nvidia, 2026-11-01): the container for the final run is not chosen by the team; "it will be based on the highest scoring submission". Host containers do not take a top-3 final-run place.
- Challenge Space (Final-run selection): at least the top 3 teams per track get final runs; nuPlan selected teams get two extra evaluation runs (Harmonizer stays off for nuPlan). Accepted submissions count even if evaluation fails.
- The Contestant Guide (e2e_challenge README, current branch) does not state the rule; #232 is the only organiser statement found, and it was asked about PAI.
- Consequence: submission order does not matter. If v9 (A) scores below W1, the W1 entry is the one that counts.

## 2026-11-12 nuPlan board read (240 entries, 60 teams; snapshot scratchpad lb_nuplan_1112.json)
- All PCS values were refit since 11-08 (same submissions moved -112..+102). W1 host 093: 2181 -> 2247, now rank 5. Our best v8 1903 (rank 41); no W1 entry of ours on the board.
- Top three entries share exactly 2279 (nu-vail-36 mean 0.988, 3.79 km/incident; SymPhi sp-1104b 0.971; sp-1029a 0.969). Looks like a ceiling or tie in the fit, not equal driving.
- Team best order (host excluded from final-run places): nuVAIL 2279, SymPhi 2279, Lucifer AI 2261 (lf-009), then a W1 entry would sit ~2247, ahead of CQUPT 2234 and 메타몽 2233.
- W1-based entries from other teams (same dist_to_gt ~0.59): CQUPT 0.9405 / 0.883 km -> -13 PCS vs W1; 메타몽 0.9395 / 0.841 -> -14; Lucifer lf-010 0.9433 / 0.929 -> -49; lf-009 0.9454 / 1.039 -> +14. So add-ons on W1 have mostly landed below it; one small gain shows as +14.
- To reach top 3, A must beat lf-009's 2261, about +14 PCS over W1. Board stays sensitive: TerraDrive 0.9205 vs 0.9202 mean -> 2182 vs 2022.

## 2026-11-12 v9 pushed (Aman)
- Before the push: CLI token refreshed (configure-token, hidden prompt); `CLI limits`: 2 official left this month (1 used), nuplan-warmup 2 left; `v9` absent from the registry; `ecr-login` OK.
- **`teams/amanupg:v9` pushed, digest sha256:da1fe936e1267f9e6ca8c5fb0a98471b5ba4d7437da7f111b497a622fb66f61d** = `local/w1n:1` (W1 + nudge A, K=3; image check passed). Next: nuplan-warmup, then the official submit if it succeeds.
- **v9 warmup submitted (Aman, 2026-11-12):** track `nuplan-warmup`, submission_id `1be2985a-7470-4ac1-9473-a0bc0a8bd002`, QUEUED 1/1. No official slot used.
- **v9 warmup SUCCEEDED (1be2985a, 18:09-18:21 UTC):** resolved digest sha256:da1fe936… (the checked image), 32/32 rollouts valid and scored, wall time 272.5 s of 2,700 s (throughput passed, margin 2,428 s). Ready for the official nuPlan submit (Aman's call).
- **v9 OFFICIAL nuPlan submission (Aman, 2026-11-12): submission_id `7946d8df-f2e5-4254-a3a7-515d5202de43`**, image `teams/amanupg:v9` (digest da1fe936…), no controller gains. QUEUED 1/1. Monthly count 2 of 3 (1 left, kept for plain W1 if v9 scores below it).
- **v9 official evaluation SUCCEEDED (7946d8df, 22:13-22:43 UTC):** 1,000/1,000 rollouts valid, wall time 1,235 s of 3,000. Status `score` 0.7038 (= dist to GT, as for v6/v8; W1 0.590, j64s0 0.669, v8 0.836). Not yet on the board at 22:47 UTC; polling.
- **v9 on the board (snapshot scratchpad lb_nuplan_1112c.json): PCS 1971 [1843, 2100], mean 0.9255, at-fault incident dist 0.712 km, dist to GT 0.704; entry rank 37 [28-45], team rank 20.** Host W1 (093) in the same refit: 2259, mean 0.9437, 0.981 km, GT 0.590. **v9 vs W1: -0.018 mean, -0.27 km per at-fault incident, about -288 PCS.** Top-3 line (Lucifer lf-009) 2273.
- Validity: same image as the closed-loop-checked local/w1n:1 (digest da1fe936…), 1,000/1,000 valid rollouts; W1 comparison is against the host's own W1 entry, which our harness reproduces (182/200 identical, line 938).
- **Verdict: nudge A hurts on the board, badly, the same way v8's start-now did (more at-fault incidents, larger GT deviation).** NuRec called the direction (its at-fault collisions after drop_wait) and local nuPlan did not (+0.012 to +0.023, zero losses): now 3 of 3 for NuRec on direction, 0 of 3 for local nuPlan. Size was not predicted by either.
- Remaining: 1 official slot this month, 1 nuplan-warmup. Plain W1 (`local/w1:1`, db5833d6…, standard garage entrypoint) is the planned use; expected ~W1's board score (~2259, team 4th behind the 3 non-host leaders) if the board is deterministic for the same driver.

## 2026-11-12 (night) Last-slot search until Nov 15 (Aman decides that day; default plain W1 as v10)
- **Proxy check (host data, agent):** only 3 board entries map to host local results (093 = waypoints s1, joint64 s0, 120 = joint32 s2), so no local metric can be validated (n = 3, 22 metrics tried; three 3/3 hits is chance level). Across all 242 board entries PCS ranks with mean scene score (Spearman 0.97) far more than with km per incident (0.76). Host research log: a change counts only if it helps on BOTH nuPlan and NuRec; "single-track gains did not transfer to the leaderboard"; run-to-run noise ~0.5 points nuPlan, ~3 NuRec.
- "Board calls the driver at 10 Hz" (host README): not relevant to nuPlan; the nuPlan challenge config fixes control_timestep_us 500000 (line 815, alpasim#155).
- **W1 failure census:** NuRec base (440): at-fault incidents 61 = off-road 42, front collision 18, lateral 1; loss shares low progress 45 %, off-road 30 %, front collision 13 %. Fresh nuPlan W1 (691): loss shares off-road 36 %, stuck 34 %, low 20 %, front collision 6 %.
- **Hybrid driven output (host 'not tried'): impossible on W1** (waypoints model has `unicycle_action_config: null`; actions need it). Only joint64 could, at ~-64 PCS start.
- **Box-based emergency brake, offline replay on W1 shadow logs** (`scratchpad/aeb_offline.py`, `aeb_timing.py`; ego box 4.9x2.0 m, constant-velocity boxes, collision with the plan within H): NuRec fires in 18/19 at-fault collision scenes and 5/194 clean (H 1.0 s), but at least 0.5 s before the collision in only 9-10/19 (lead mostly 0.5-0.8 s); nuPlan catches 0/3 collisions (boxes missed) and fires in 7/469 clean scenes. Front collisions are 6 % of nuPlan loss. Expected board effect small; not built yet.
- **Candidate 1, waypoints 3-seed ensemble (s0+s1+s2, plans averaged):** host seeds share most failures (35 of W1's 62 public incidents in all three), so the upside is limited, but it is the only whole-policy change left with a broad mechanism. Launched: nuPlan fresh parts 002/004/006/008/009/012/015 with W1 and E3 paired in one job (13883425-31, `sim_nuplan_multi.sbatch` now takes `CKPTS_<variant>`); NuRec 12 chunks (13883432-43, TAG wpe3), paired against the W1 base pass. Gate (host rule + ours): better on both NuRec and fresh nuPlan, no more at-fault incidents on either, beyond rerun noise.
- **Capacity:** R6000 nodes: ins046 draining for a reboot, ins047 busy with a reserved 4-GPU job; NuRec start unknown. nuPlan starts estimated 18:23 EST tonight to 09:25 tomorrow.
- **Research sweep (agent):** organisers published per-scene private-set scores for 36 September board entries (alpasim PR #228, `e2e_challenge/local_evaluation`); private nuPlan set = ~20 log segments cut into ~1,000 overlapping starts, so one failure situation zeroes 5-15 scenes (fits v8/v9 losing in lumps). Not to be used to fetch or tune on those logs. Drive-IRT: PCS from per-scene scores only, zeros cost most on scenes strong entries pass; km/incident only breaks rank ties. No public trick found that beats W1.
- **Candidate 2, moving-only slow-down (`src/g2_slow`, G2_SLOW_F, G2_SLOW_VMIN 2.0 m/s):** plan retimed to F of its speed when the ego moves >= 2 m/s (same path and stop points, reached later); untouched from rest. Rationale: the board punished both assertive add-ons; full score at 80 % progress. Unit check: 10 m/s straight -> 9 m/s, stop point kept, heading wrapped.
- Relaunched nuPlan as one job per fresh part with W1 / E3 / S9 (F 0.9) / S85 (F 0.85) paired on one GPU: 13883484-90 (cancelled 13883425-31 before start; `sim_nuplan_multi.sbatch` takes `ENV_<variant>`). NuRec S9: 13883491-502 (TAG w1s9). NuRec E3 13883432-43 unchanged.

## 2026-11-12 (late) Candidate 1 (waypoints 3-seed ensemble) fails on NuRec
- NuRec, 4 of 12 chunks (147 scenes) vs the W1 base pass: **-0.0227 [-0.069, +0.024], W25 / L57**, new zeros 6, fixed 7. Noise floor (W1 rerun vs the same base, 167 firing-set scenes): -0.013, W45 / L35, new 5 / fixed 3. The loss/win ratio is far outside rerun noise. **Verdict: fails the NuRec half of the gate; dropped.** Remaining E3 NuRec chunks cancelled (13883436-43); nuPlan parts 008/009/012/015 resubmitted with W1 / S9 / S85 only (13887503-06; cancelled 13883487-90 before start). Parts 002/004/006 still run E3 on nuPlan, for the record.
- Ops: fresh-part downloads from HF run at ~3 MB/s (~2 h per part); `cluster/fetch_parts.sbatch` pre-fetches parts in parallel to `data/mtgs_parts` (13885759), `sim_nuplan.sbatch` uses the cache and builds a part once per multi job. NuRec jobs need only ~13 GB host memory: requests cut to 15 GB so they fit on ins047.
- **Candidate 3, slow-down in turns only (`G2_SLOW_CURVE_DEG`, SC = F 0.8 when the plan turns > 15 deg within 3 s, ego >= 2 m/s).** Offline on W1 shadow logs, share of moving plans turning > 15 deg: nuPlan off-road scenes 0.59 vs clean 0.24; NuRec off-road 0.21 vs clean 0.07 (collisions 0.19). Launched: nuPlan parts 002/004/006 W1 vs SC (13887521-23); NuRec 12 chunks (13887524-35), interleaved with S9's later chunks by the release script.
