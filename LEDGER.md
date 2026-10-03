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
