# Resume source record: alpasim-jepa (AlpaSim E2E Closed-Loop Challenge 2026, nuPlan track) (TRACK CLOSED)

Compiled 2026-11-21 for Aman (au2327, Columbia) as raw material for resumes; round 2 of the 2026-11-13 file (`notes/resume_source_2026-11-13.md`). Lossless, not a summary; raw facts plus keywords, to be trimmed by a separate resume agent. Section numbers 0-14 keep the Nov 13 labels; section 15 (keyword list) is new.

**Track status: CLOSED.** Final entry v10 (plain released W1), submitted 2026-11-15 ~08:20 UTC. PCS 2320 [2155, 2485] on the 2026-11-15 10:36 UTC board; PCS 2450 [2303, 2597] on the final board read 2026-11-21 ~23:06 UTC. **Official final rank: 18th on nuPlan** (per Aman; the final board's team order by best-entry PCS gives the same, 18 of 63 teams). Technical report accepted 2026-11-16 22:57 UTC.

Sources, in order of authority: `LEDGER.md` (1,210 lines, last entry 2026-11-16 22:57 UTC), git history (317 commits, last 8c7715a 2026-11-16 17:57 EST), the public leaderboard endpoint read 2026-11-21 (`/leaderboard?track=nuplan`, 291 records, saved as session scratchpad `lb_nuplan_1121.json`), `report/amanupg_nuplan_report_final.tex` (the accepted report), `notes/storage_assessment_2026-11-16.md`, `notes/nov15_summary.md`, file listings, memory notes, the 2026-11-13 resume file, and `../LESSONS_FOR_AGENTS.md`. GPU-hours (541.2) are from sacct as given by the PAI agent / Aman. Where sources disagree, LEDGER and the board JSON win and the conflict is listed in section 14. Nothing in this file is a credential.

---

## Changed since 2026-11-13

Everything below is also merged into the numbered sections; this list is the delta.

### A. Last-slot search, finished (11-13 to 11-15)
- SC (speed cap 0.8 in turns > 15 deg) on full NuRec (440): +0.0002 [-0.012, +0.012], W86/L95, new zeros 3, fixed 6; at-fault incidents 58 vs 61; with nuPlan +0.0002 (691): no measurable effect. (Nov 13 file said "NuRec untested"; now tested.)
- ST (cap 0.6 in turns > 10 deg): nuPlan (300) -0.0079 [-0.015, +0.001], W4/L43; NuRec (440) -0.0042 [-0.020, +0.011], W76/L106, at-fault 52 vs 61 (off-road 35 vs 42), corridor exits 12 vs 9. Fewer incidents, less progress; dropped.
- 11-13 afternoon checks: route-agreement guard (offline) not viable (about 5 clean scenes flagged per off-road scene); low-progress anatomy (fresh 691: 571 score 1, 63 low, 25 stuck, 32 zeros; slow acceleration from low speed, the family v8/v9 targeted and the board punished).
- 11-13 evening: deep-research workflow (101 agents, 19 sources, 25 claims verified, 6 killed) and LinkedIn sweep (Aman's login): Alpamayo 2 Edge assessed and not pursued; SimWAM, ZTRS, verifier/Best-of-N methods assessed, none fits; KE:SAI's on-policy distillation announced but not released.
- 11-13 night to 11-14: on-policy distillation (DAgger) of W1 with a sampler-exact ("served plan") loss. Pooled on 691 fresh nuPlan scenes vs W1: D1 -0.0358 [-0.053, -0.019] (at-fault 4 -> 9), D1o -0.0036 [-0.0076, -0.0003], D2h -0.0053 [-0.011, -0.000], **D2o +0.0025 [-0.0015, +0.0068], W64/L22, at-fault 4 -> 4** (CI includes 0; does not pass). D2o NuRec never ran (R6000 GPUs blocked; jobs cancelled 11-15).
- 11-14/15: route leash (our reading of CQUPT's entry name): L03 -0.0072 [-0.0132, -0.0014], L05 -0.0016 [-0.0059, +0.0027], L10 -0.0000 on 691 fresh scenes. Negative; rejects our reading, not CQUPT's method.

### B. v10 submission and result
- v10 = plain W1 (`local/w1:1`), no add-on, standard garage entrypoint. Pushed 2026-11-15 as `teams/amanupg:v10`, digest sha256:db5833d60444c06e74381d111f71f96c84260676de344fba86d53590927ad388. I ran push/warmup/submit on Aman's instruction; Aman entered the CLI token himself via the hidden prompt.
- Warmup 77c74265-bfdb-461f-98f5-bf2ded67ffb0: SUCCEEDED 08:06-08:18 UTC, 32/32 valid, 269.6 s of 2,700 s.
- Official 2f9b4489-37d9-435b-9832-71f45421c6ea: SUCCEEDED 08:20-08:49 UTC, 1,000/1,000 rollouts valid, 1,194.5 s of 3,000 s; dist to GT 0.58975 (identical to host W1 093, so the same driving).
- BOARD 11-15 10:36 UTC: PCS 2320 [2155, 2485], entry rank field 13, mean 0.93955, 0.841 km per at-fault incident. Host W1 093 in the same refit: 2332, mean 0.94369, 0.981 km. Same GT distance, different mean: board runs are not bit-identical across runs of the same driver.
- BOARD final (read 11-21): PCS 2450 [2303.4, 2596.9], entry rank field 37 [6-60], mean 0.93955, 0.841 km, GT 0.58975. v10 is the team best (+359 over v9 2091 in the same refit).
- November slots: 3 of 3 used (v8, v9, v10). Official entries total 5 (v0.3, v6, v8, v9, v10).

### C. Report upload and acceptance
- Final report `report/amanupg_nuplan_report_final.pdf` (4 pages, LaTeX built with tectonic, NeurIPS-2026-derived organiser style): "Local Gains That Did Not Transfer: Closed-Loop Lessons From Adapting a Released Latent TransFuser" (AlpaSim E2E Closed Loop Challenge Technical Report, nuPlan track). Author: Aman Upganlawar, Columbia University. Sections: final policy; resources, training and runtime; evaluation protocol; what we tried and what the board said; sampler-exact on-policy distillation; limitations and safety.
- Uploaded 2026-11-16 22:57:16 UTC after Aman reviewed it and refreshed the CLI token himself: report_id a135197d-95b7-4066-8b9f-32a6f24c63eb, status ACCEPTED, sha256 511e2d836139cea329145562b861a5646ba0ea1b490c8cc02760adc9d54ebdc2, 45,330 bytes. Before the Nov 16 AoE deadline.
- The report quotes the 11-15 board (PCS 2320), not the final refit (2450).

### D. Final standings (board read 2026-11-21 ~23:06 UTC; 291 records = 286 submissions + 5 organiser final runs; 63 teams, 6 host-labelled, 57 non-host)
- **Official final rank (per Aman): 18th on nuPlan.** Board check: team order by best submission PCS, all 63 teams, puts amanupg 18th (v10 2450).
- Other framings, labelled (not the official rank):
  - 17th of 57 non-host teams (same board; host py123d-garage 093 at 2478 is the only host team above us).
  - 5th among prize-eligible teams on the 2026-11-15 10:36 UTC board (LEDGER line 1198; team order then CQUPT 2370, SymPhi 2370, nuVAIL 2360, Lucifer 2350, [host 2332], us 2320, 메타몽 2319). Superseded by later submissions (37 board records dated after that read: 32 submissions 11-15 to 11-17 plus the 5 organiser final runs of 11-18) and by refits.
  - Entry rank field: 13 (11-15), 37 with interval 6-60 (final). The rank field is not plain PCS order (see 14.1); by PCS v10 is the 40th of 291 records.
- Final top 18 by best-entry PCS: 1 SymPhi sp-1029a 2573 (mean 0.9693); 2 CQUPT Huixin Jimu `geo1134-turngate30-pathonly-leash-20261113-v2` 2547 (0.9677); 3 nuVAIL nu-vail-486 2546 (0.9862); 4 Lucifer AI lf-013 2528 (0.9494); 5 Zeron-VLA 2499; 6 Team-WAM 2497; 7 wam-cbf (one-wam) 2496; 8 tongji_zero (my-drive-cosmos) 2495; 9 M-Mark 2495; 10 tjnh (wam) 2491; 11 wam-cbf (one-wam2) 2491; 12 Economou-love 2483; 13 EML (team-wam) 2482; 14 py123d-garage host 093 = W1 2478 (0.9437); 15 lollipop 2471; 16 tree-high 2467; 17 메타몽 metamong-1103a 2455 (0.9395, 0.841 km, i.e. the same numbers as v10); **18 amanupg v10 2450**. Next: BlindDrive 2448, TerraDrive 2444, Team gh 2444 (plain joint64 seed 0 entries).
- Organiser final runs ("Noise reduction: 3-run mean", backend `organizer-noise-reduction-mean3`, posted 2026-11-18 14:26 UTC) exist for 5 teams: SymPhi sp-1029a 2573, CQUPT 2546, nuVAIL 2546, Lucifer lf-009 2513, 메타몽 metamong-1103a 2454. **amanupg did not get final runs.** Why 메타몽 (2319 at 11-15 10:36, 1 PCS below us) got one and we did not is not documented (see 14).
- Rank movement 11-15 -> final: 10 teams with entries submitted 11-16/17 (Zeron-VLA, Team-WAM, wam-cbf x2, tongji_zero, M-Mark, tjnh, EML, nuVAIL's new best, Lucifer lf-013) and refits (Economou-love 2268 on the 11-15 08:50 read, now 2483 with mean 0.9249 vs our 0.9395) moved us from 6th by team (5th eligible) to 18th. Several of the new entries share mean 0.9289 / 1.472 km (likely one shared base, not verified).
- Our other entries in the final refit: v9 2091 [1935, 2247], v8 2069 [1925, 2212], v0.3 1381 [1310, 1451], v6 1218 [1153, 1282].

### E. Cluster cleanup (2026-11-15/16)
- 11-15 ~11:00 UTC: remaining D2o NuRec jobs (13907535-41) cancelled on Aman's instruction; no alpasim-jepa jobs left.
- Storage assessment `notes/storage_assessment_2026-11-16.md` (folder-by-folder keep/delete; KITScenes reuse judged: none useful). Archived to the Mac (`cluster_archive/`, gitignored, 1.2 GB): per-scene aggregates of all 616 runs (2,461 files, 217,926,427 bytes), DAgger decoder D2o (273 MB), W1 weights folder (817 MB; Apache-2.0 at HF revision 56edbe90). Counts and sha256 matched. Cluster-only code committed (0be9808): `cluster/audit_cmp.sbatch`, `src/tools/compare_runs.py`, `src/tools/summarize_run.py`, `analysis/pool_scripts/{pool_fresh,pool_nurec,pool_dagger,leash_unit}.py`.
- `/insomnia001/depts/edu/users/au2327/alpasim-jepa` (1.4 TB, 756,691 files) deleted by Slurm job 13924597 (18 min, 2026-11-16 ~02:30 UTC); department fileset 8.1 TB -> 6.7 TB used (of 10 TB). Left for Aman: revoke the HF token that sat in the deleted `.cache/hf/token`; `~/.cache/nre` (1.4 GB NuRec cache in home) not deleted.

### F. Scale (new number)
- Cluster GPU use for alpasim-jepa: **541.2 GPU-h** (sacct, all runs incl. requeues, as of 2026-11-16 15:41 EST; final, since the folder was deleted that day). No RunPod, Vultr or other rented compute for this thread ($0); Vultr was checked 11-13 with Aman logged in (all L40S/H100 plans unavailable) and nothing was deployed. Mac: Docker builds and image checks only.

### G. Corrections to the 2026-11-13 file
1. Section 2 "Best entry v9 1971" and "planned v10, not submitted": superseded; v10 submitted, team best (2320 on 11-15; 2450 final).
2. Section 2 forecast "plain W1 should land near the host's 2259, about 4th non-host": actual 2320 vs host 2332 in the same refit (11-15), 5th eligible then; final 18th overall / 17th non-host.
3. Section 3 "SC: NuRec untested": tested 11-13, no effect (A above).
4. Section 6 "GPU-hours: not recorded in aggregate": now 541.2 GPU-h (F).
5. Section 8 git: 284 commits -> 317 (Sep 25, Oct 181, Nov 111); tracked files 139 -> 158.
6. Section 14.3 (deadline): resolved; report accepted 11-16 22:57 UTC, before Nov 16 AoE.
7. Section 14.20 (report): resolved; the final report describes v10 and was accepted.
8. Section 13 bullets quoting "PCS 1971, team rank 20/62": replace with the final numbers (section 13 below).
9. LEDGER line 1198 says "+311 over v9 2009" while the 08:50 UTC read had v9 at 1985; both are true for their refits (10:36 vs 08:50).
10. Nov 13 section 14.1 noted that the rank field is not PCS order; still true in the final board (v10 rank field 37, PCS position 40).

---

## 0. Labels used for every number

| Label | Meaning |
|---|---|
| BOARD | Official leaderboard, private nuPlan test set (~1,000 scenes), one evaluation run per submission. PCS intervals are the board's 95% posterior intervals. Board values are refit as entries arrive, so the same entry's PCS changes over time; the date of each read is given. |
| WARMUP | Official server-side warmup (32 rollouts, unscored smoke test, never on the board). |
| L-tune | Local closed loop on public nuPlan navtest scenes, tuning pool: MTGS asset parts (shards) 001 / 010 / 005, n = 300. Used to choose settings. |
| L-held | Local, held-out pool: parts 013 (100) / 007 (61) / 011 (100), n = 261. Used to confirm, and later to choose once (R2). |
| L-fresh | Local, scenes never used for any choice at the time: Oct: parts 003 (93) / 014 (100), n = 193. Nov: parts 002 / 004 / 006 / 008 / 009 / 012 (n = 600) and 015 (n = 91), n = 691 total. |
| L-early | Local results before the tuning/held-out protocol existed (shards 001 and 010 only, Sep 29 to Oct 1). |
| NuRec | Local closed loop on NuRec scenes (NVIDIA PAI-AV neural reconstructions rendered by the NRE renderer; 441 curated val scene ids, 440 usable), run with py123d v0.2's NuRec rig. Not bit-repeatable run to run. |
| OL | Open-loop offline metrics (ADE / FDE / lateral error) on nuPlan val samples. |
| HOST-PUB | The host's published per-scene results (HF `kesai-labs/py123d_garage_pretrained_checkpoints`, `v0.2.0/<model>/results/nuplan/seed_<n>`) on 1,485 public navtest scenes. |
| PAI-local | Local closed loop on the PAI track (40 curated val scenes). |
| PROXY | Our local refit of the board's Drive-IRT zoib model (PCS proxy) on our own per-scene scores. |

Unless stated otherwise, local "diff [a, b]" is a paired per-scene difference in mean scene score with a 90% bootstrap interval, and "W / L" is per-scene wins / losses. "Zeros" are zero-score scenes. "Big W / L" are per-scene changes larger than 0.5.

---

## 1. Challenge and track context

### Organisers and venue
- NVIDIA AlpaSim End-to-End Closed-Loop Challenge 2026 (HF Space `nvidia/AlpasimE2EClosedLoopChallenge2026`). Hosted by NVIDIA AV Research, KE:SAI (py123d-garage, the host team on the board) and HKU OpenDriveLab. Results at the World Models in Physical AI workshop, NeurIPS 2026 (as given in the brief; the ledger does not restate the workshop name).
- Two tracks: PAI (NVIDIA PAI-AV scenes, NuRec/NRE renderer) and nuPlan (Motional nuPlan scenes, MTGS renderer). Team `amanupg` (Aman is captain; HF account `amanupg-columbia`). This thread (alpasim-jepa) owned nuPlan; the sibling thread (`../alpasim`, Alpamayo) owned PAI.
- Contestant code base: NVlabs/alpasim, branch `e2e_challenge` (our first pin 2023534, Sep 18; the competition ran e121e59; the diff is only a lateral-corridor scorer fix, issue #198, plus a report-upload CLI).

### Benchmark (nuPlan track)
- Private nuPlan test set, ~1,000 scenes. From the organisers' per-scene release (alpasim PR #228): ~20 log segments cut into ~1,000 overlapping start times, so one failure situation can zero 5 to 15 scenes at once (fits v8/v9 losing "in lumps"). Organisers (#191): the set is "unpublished anywhere", distribution close to the public one. Per-scene private data from PR #228 was deliberately not used to fetch or tune on those logs.
- Public dev data: `OpenDriveLab/AlpasimChallenge2026_nuplan_track` (~491 GB total, public; navtest scene configs 1,491 over 44 logs; MTGS asset parts of ~100 scenes, ~32 to 35 GB each).
- Sensors delivered: 8 cameras at 1920x1080, 2 Hz (0.5 s steps). Control step fixed at 500 ms (alpasim #155; `control_timestep_us: 500000`), so replan rate is not a lever on nuPlan.
- Scene scoring (e121e59 configs): 4 s scored after a 0.5 s log replay; decisions every 0.5 s; score 0 on at-fault collision, off-road, or lateral corridor exit, else min(1, progress / 0.8), full score if the GT moved < 5 m; progress stops once > 4 m from the GT path or at any collision; trafficsim skipped (other agents replay the log, non-reactive).
- Harmonizer: off for nuPlan, both on the board and in final runs (verified our local nuPlan runs match: `--enable-harmonizer` exists only in the NRE/PAI renderer command).

### Metric
- Primary: Policy Capability Score (PCS) from Drive-IRT, a zero-one-inflated beta (zoib) item-response model fitted over all entries' per-scene scores (`metric_algorithm: zoib`). PCS comes from per-scene scores only; zeros cost most on scenes strong entries pass. Board columns also show average scene score, rank spread, average km between at-fault incidents (the tie-breaker), and distance to the GT trajectory. The CLI's status `score` field is distance to GT, not PCS (easy to misread).
- Measured on the 11-12 board (agent analysis, 242 entries): PCS ranks with mean scene score (Spearman 0.97) far more than with km per at-fault incident (0.76). PCS is not monotone in the mean (e.g. 11-04: SymPhi 0.969 above nuVAIL 0.982), and very sensitive near the top (TerraDrive 0.9205 vs 0.9202 mean: PCS 2182 vs 2022 on 11-12; terra-drive j64s0 v2 vs v3: 0.0003 mean apart, 149 PCS apart on 11-08).

### Deadlines and limits
- **nuPlan track CLOSED** (submissions and reports closed Nov 16 AoE). Our final: v10 PCS 2450 (final board, read 2026-11-21) / 2320 (2026-11-15), official final rank 18th; report accepted 2026-11-16. PAI track closed 2026-10-31 (sibling thread).
- Original: leaderboard close and final container choice 2026-10-31, 4-page technical report per track by Oct 31.
- Organiser email 2026-10-23: nuPlan submissions and report deadline moved to **2026-11-16 AoE** because py123d_garage v0.2.0 was released ~2026-10-22 (alpasim #221). Winners targeted 2026-11-23 for nuPlan; first-place and innovation winners make a 3-minute video by 2026-12-03. PAI closed 2026-10-31.
- Official submissions: 3 per calendar month, shared by both tracks; unused slots expire at month end. In November all 3 were effectively nuPlan's.
- Warmups: 3 per warmup track per rolling 30 days; unscored smoke tests (32 rollouts, 2,700 s limit, 45-minute simulation limit); they validate only the form factor.
- Container contract: image <= 40 GiB; <= 16 GiB VRAM per replica; no network; read-only root, writable `/tmp` 2 GiB and `/run` 64 MiB; evaluation GPU H100 (#189); "0.1 s of model work per Drive call" enforced as a per-track throughput budget (nuPlan: 3,000 s wall time for 1,000 rollouts).
- Final runs (Space + #232): at least the top 3 teams per track get final runs; nuPlan finalists get 2 extra evaluation runs, Harmonizer off. Host containers do not take a final-run place. Organiser mwatson-nvidia (#232, asked about PAI, 2026-11-01): the final-run container "will be based on the highest scoring submission", so submission order does not matter. Accepted submissions count even if evaluation fails.

### Rules that shaped the work
- Prize eligibility on nuPlan: "Award-eligible nuPlan submissions may use only publicly available datasets, annotations, and model weights." #184 (organiser): data derived from public data (including generated rollouts from the provided nuPlan test split) is public. Host entries are excluded from prizes. The innovation award is judged from the reports, "on any baseline".
- Terms `official-2026-08` (sha256 8166fed2…, accepted by Aman 2026-09-27): §3 public data only on nuPlan, comply with dataset terms; §5 submissions under Apache-2.0 with the licence notice included, third-party components Apache-compatible "and properly identified" (led to `container/LICENSE` + per-image `NOTICE` files); §8(c)/§13 no third-party IP infringement. Residual grey area noted, not resolvable by us: nuPlan's CC BY-NC-SA data licence vs the commercial rights §5 grants NVIDIA (shared by the organisers' own SimScale samples).
- Evaluation integrity: the driver uses only what the RPC delivers (cameras, ego pose/dynamics, route); `debug_info.scene_id` is forbidden; the private set is never touched.
- Neutral image tags (our own rule): tags are public on the board, so they are plain sequence labels (v4, v5, ...), never method names. One earlier pushed tag broke this (`nuplan-wajepa-judge-6672747`, pushed 10-02/03 before the rule).
- Reporting: award eligibility needs a final valid submission plus the 4-page report; it must credit public resources and licences.
- Team-internal rules: Aman pushes, warms up and submits; adopt only gains confirmed paired on scenes not used to choose them; after v6, never project local navtest gains of NAVSIM-trained parts; after v9, never submit an add-on on local nuPlan gains alone.

---

## 2. Outcome

### FINAL outcome (track closed; board read 2026-11-21 ~23:06 UTC)
- **Official final rank: 18th on nuPlan (per Aman; = team order by best-entry PCS on the final board, 18 of 63 teams).**
- Final entry v10 (plain released W1): PCS 2450 [2303.4, 2596.9] final refit; 2320 [2155, 2485] on 2026-11-15 10:36 UTC. Mean scene score 0.93955, 0.841 km per at-fault incident, dist to GT 0.58975, 1,000/1,000 valid, 1,194.5 s of 3,000 s.
- Other framings (labelled, not the official rank): 17th of 57 non-host teams (final board); 5th among prize-eligible teams on the 11-15 10:36 UTC board (LEDGER); entry rank field 13 (11-15) and 37 [6-60] (final).
- No organiser final runs for amanupg (given to SymPhi, CQUPT, nuVAIL, Lucifer, 메타몽).
- Technical report accepted 2026-11-16 22:57 UTC (report_id a135197d-95b7-4066-8b9f-32a6f24c63eb).
- Our five official nuPlan entries, final refit: v10 2450 [2303, 2597]; v9 2091 [1935, 2247]; v8 2069 [1925, 2212]; v0.3-a15int8-1hz 1381 [1310, 1451]; v6 1218 [1153, 1282].

| Tag | Submitted (UTC) | Submission id | Image digest | What it is | Run | BOARD 11-15 10:36 | BOARD final (11-21) |
|---|---|---|---|---|---|---|---|
| v10 | 2026-11-15 ~08:20 (eval 08:20-08:49) | 2f9b4489-37d9-435b-9832-71f45421c6ea | sha256:db5833d60444c06e74381d111f71f96c84260676de344fba86d53590927ad388 (= local/w1:1) | released py123d v0.2.0 waypoints posttrain seed 1 (W1), unmodified | 1,000/1,000, 1,194.5 s | PCS 2320 [2155, 2485], rank field 13, mean 0.93955, 0.841 km, GT 0.58975 | PCS 2450 [2303.4, 2596.9], rank field 37 [6-60], same mean/km/GT |

Warmup for v10: 2026-11-15 08:06-08:18 UTC, 77c74265-bfdb-461f-98f5-bf2ded67ffb0, SUCCEEDED, 32/32, 269.6 s of 2,700 s.

The subsections below are the 2026-11-13 record, kept for history (their standings are superseded by the final outcome above).

### Official nuPlan entries of team amanupg (all four on the board)

| Tag | Submitted (UTC) | Submission id | Image digest | What it is | Run | BOARD at submission | BOARD 2026-11-12 (snapshot 1112c) |
|---|---|---|---|---|---|---|---|
| v0.3-a15int8-1hz | 2026-09-29 18:26 | 491ce993-ed61-4c43-ad08-a9968aa3bce9 | (in ../alpasim ledger) | Alpamayo 1.5 int8, 1 Hz inference (submitted by the PAI thread before this thread existed) | used 1,268 s of 3,000 | PCS 1296, rank 19/71 entries, mean 0.827 | PCS 1370 [1298.7, 1442.1], rank 92 [84-99], mean 0.8375, 0.234 km/at-fault incident, GT 1.278 m |
| v6 | 2026-10-21 | 9ec0413f-42e9-4cf0-9c27-d5380339fa84 | sha256:0d13aceb9285c368271f057b32914a8cc01b04f2e6e00b669d3e57c5fef14871 (= local/q:3) | py123d v0.1 fine-tune A + GTRS-Dense critic (m3, R3) + 1.10 straight-only time warp + stall rescue 3 m | 1,000/1,000 rollouts, 1,189 s of 3,000 | PCS 1131 [1076, 1186], rank 48 (interval 46-60), mean 0.782, 0.324 km, GT 1.766 m | PCS 1189 [1128.3, 1249.7], rank 114 [105-132], mean 0.7865, 0.3245 km, GT 1.766 m |
| v8 | 2026-11-08 20:00:33 | fcd5b9dd-52d6-4722-bb5c-24c6726f596e | sha256:5ea4001e7879bdb870784efd1e46c7e1879ebebbd87f13c482e9bad436cd5ab8 (= local/n2:1) | released py123d v0.2.0 joint64 posttrain seed 0 + start-now K=3 rule | 1,000/1,000, 1,145 s | PCS 1854 [1738, 1969], mean 0.9086, 0.682 km, GT 0.836 m; entry rank 33 [25-38]; team rank 18 of 58 | PCS 1928 [1814.7, 2041.5], rank 40 [32-46], mean 0.9086, 0.682 km, GT 0.836 m |
| v9 | 2026-11-12 (eval 22:13-22:43) | 7946d8df-f2e5-4254-a3a7-515d5202de43 | sha256:da1fe936e1267f9e6ca8c5fb0a98471b5ba4d7437da7f111b497a622fb66f61d (= local/w1n:1) | released py123d v0.2.0 waypoints posttrain seed 1 ("W1") + stall nudge A (K=3) | 1,000/1,000, 1,235 s | PCS 1971 [1843, 2100], mean 0.9255, 0.712 km, GT 0.704 m; entry rank 37 [28-45]; team rank 20 | same read (1971 [1842.5, 2100.0], rank 37 [28-45]) |

Intermediate BOARD reads of the same entries (refits): v0.3 1284 (rank 20/80, 10-02), 1290 (team view 8th of 28 teams, 10-02), 1298 [1233-1363] rank interval 37-44 (10-21), 1358 (11-04); v6 1182 (11-04); v8 1903 (rank 41, 11-12 first snapshot). The mean scene scores of v0.3 (0.827 to 0.8375) and v6 (0.782 to 0.7865) moved, most likely with the organisers' corridor re-evaluation of 10-22 (inferred, not verified).

### Warmups (WARMUP, unscored)
| Date (UTC) | Image | Submission id | Result |
|---|---|---|---|
| 2026-09-27 | not recorded in this thread (first nuplan-warmup of the window; PAI thread) | | |
| 2026-10-02 05:47-05:55 | `alpasim-jepa/wajepa:v2-judge-6672747` pushed as `teams/amanupg:nuplan-wajepa-judge-6672747`, digest sha256:dde3c672… | 323ebec6-1705-4104-be10-4e3ffef3f152 | SUCCEEDED, 32/32 valid, wall time 271.6 s of 2,700 s |
| 2026-10-21 20:25-20:37 | v6 | 4b849e1d-970a-496a-8fb1-2d7a996033f3 | SUCCEEDED, 32/32, 268.5 s of 2,700 s |
| 2026-11-12 18:09-18:21 | v9 | 1be2985a-7470-4ac1-9473-a0bc0a8bd002 | SUCCEEDED, 32/32, 272.5 s of 2,700 s |

The WA-JEPA + judge image (reserved tag `v4`) passed its warmup but was never submitted officially.

### Best entry and standing (BOARD, snapshot 1112c, 2026-11-12) (HISTORICAL, superseded by the FINAL outcome above)
- Best entry: **v9, PCS 1971 [1843, 2100], mean scene score 0.9255, 0.712 km between at-fault incidents, 0.704 m to GT; entry rank 37 of 242 entries [28-45].**
- Field: 242 entries from **62 distinct teams** (6 of them host-labelled: py123d-garage, Host, OpenDriveLab-Org, Anonymous, Alpain Autonomy, Valeo.ai; 50 host entries), so 56 non-host teams.
- Team rank by best entry PCS: **20 of 62** (19 of 56 non-host teams). On 11-08 (v8): team rank 18 of 58.
- Top of the board (1112c, best entry per team): SymPhi sp-1029a 2288 (mean 0.9693); nuVAIL nu-vail-36 2287 (0.9883, 3.788 km); Lucifer AI lf-009 2273 (0.9454, 1.039 km); host py123d-garage 093-nuplan-v1 2259 (0.9437, 0.981 km, GT 0.590; this is W1 unchanged); CQUPT 2250 (0.9405); 메타몽 2246 (0.9395).
- Board controls for our two add-ons:
  - Four other teams submitted the released joint64 seed 0 unchanged (team-gh, TerraDrive, Apex Autonomous, tongji_zero): identical mean 0.9205, 0.834 km, GT 0.669 to 0.671; PCS 2074-2083 on 11-08, 2191-2199 on 11-12. v8 = that checkpoint + start-now: -0.012 mean, -0.15 km per incident, +0.17 m GT, about -225 PCS (11-08).
  - Host W1 (093) unchanged: 2259 on 11-12. v9 = W1 + nudge A: -0.018 mean, -0.27 km per incident, about -288 PCS.
- So our best entry sits **below the unchanged released checkpoints it was built on**. The jump from v0.3 (1370) to v9 (1971), +601 PCS in the same refit, comes from switching to the host's released py123d checkpoints, not from our add-ons, which cost ~225 to 288 PCS each time. This must be stated honestly anywhere the 1971 is used.
- Status (2026-11-13): 1 official slot and 1 nuplan-warmup left. Default plan: plain W1 (`local/w1:1`, image id db5833d60444, standard garage entrypoint) as `v10`; Aman decides on Nov 15. If the board is deterministic for the same driver, W1 should land near the host's 2259 (team ~4th by best entry behind the three non-host leaders, i.e. inside the top-3 non-host final-run range only if a leader drops; on 11-12 the non-host top-3 line was Lucifer lf-009 at 2273). Report: the 10-21 draft describes v6 and is not updated; whether a report will be submitted is open.

---

## 3. Full chronological timeline

Every approach, experiment and pivot, with motivation, result (labelled), and why kept or dropped. Job ids are Insomnia Slurm ids.

### 2026-09-29 Start: why JEPA, for which track
- Context: the team's driver (`../alpasim` v0.3, Alpamayo 1.5 int8, no reasoning) was PAI PCS 2143, rank 2/58 [BOARD, PAI] and nuPlan PCS 1296, rank 19/71 [BOARD]. Alpamayo is off-domain on nuPlan (NVIDIA 10 Hz rig vs Motional 2 Hz rig); its at-fault spacing 0.234 km was below go-straight's 0.258 [BOARD]. Eligible teams ahead sat ~1463-1469.
- Idea: released JEPA planners are built for the nuPlan contract (NAVSIM: Motional cameras, 2 Hz, 8 waypoints at 0.5 s) with public weights, which keeps prize eligibility. Compared WA-JEPA (arXiv 2608.20974: V-JEPA 2.1 ViT-L + joint flow predictor denoising future scene tokens and ego trajectory; NAVSIM v2.2 navtest EPDMS 91.7; HUGSIM HD-Score 0.4462; Apache-2.0) and Drive-JEPA (arXiv 2601.22032; NAVSIM v1 PDMS 93.3, v2 EPDMS 87.8; CC0 weights).
- Read WA-JEPA's input contract from its configs and reference adapters (cameras l0/f0/r0/b0 order-sensitive, 256x512 INTER_AREA, [-1,1], 4 history frames 0.5 s apart, ego status = command one-hot(4) + vx, vy, ax, ay, 4-pose history, output 8x(x,y,yaw); fp32 weights under bf16 autocast, since bf16 weights do not reproduce). Recorded the authors' silent-failure checklist.
- Evaluation plan approved by Aman: offline sanity, 100-scene paired local closed loop vs Alpamayo v0.3, nuPlan-only image, warmup, October slot.
- Built `src/wajepa_challenge/` from the organisers' NAVSIM sample (Apache-2.0): modified `driver.py` (4 cameras x 4-frame history, pose history, resize on arrival, counters) + our `preprocessing.py` and `policy.py`. CPU smoke test: strict checkpoint load, **788 M parameters**, ~3.2 GB fp32, load 14 s, one CPU plan 29 s; frame/speed conventions checked with a synthetic 5 m/s straight history (plan ~4.6 m/s straight). `tests/test_driver_history.py` (simulated gRPC traffic, fake policy) 2/2 pass.
- Insomnia setup (Aman: "option A, use Insomnia"): WA-JEPA @ bec2966, weights HF `AFARI-Research/WA-JEPA` @ 15c0770e (sha256 e1d3be01…6408); borrowed envs/simulator read-only; own Apptainer launcher `src/compose_apptainer.py` that mounts the sibling tree read-only.
- GPU check (job 12994593, L40S, driver 550.54): **0.202 s per plan** (p90 0.203) at batch 1, 0.408 s at batch 2 (no batching gain), 6,114 MiB process memory (peak reserved 5.47 GiB). Alpamayo v0.3: 0.83 s / ~14.5-15 GB.
- **Closed loop WA-JEPA vs Alpamayo v0.3, same 100 shard-001 scenes** (job 12994594, 22 min 39 s) [L-early]: mean scene score 0.958 vs 0.759; passed 96 vs 82; at-fault collision 0.00 vs 0.03; offroad 0.03 vs 0.06; left corridor 0.01 vs 0.11; progress 0.98 vs 0.85; dist to GT 1.01 vs 1.80 m; Drive call 0.215 vs 0.41 s; 5.4 vs ~14.5-15 GB. Paired **+0.198 [+0.131, +0.265], W35 / L2 / T63**. Driver health: 1,000 calls all model inference, 0 fallbacks, 0 errors.
- Validation ("check again rigorously", Aman) [L-early]: config parity of all service configs; no train/test overlap (all 4 shard-001 logs in navtest, none in navtrain); deterministic rerun identical on all 100 scenes; cameras blanked to grey 0.392 (-0.368), so it uses the cameras; constant velocity 0.578 (-0.181); **held-out shard 010 (4 other logs): WA-JEPA 0.729 vs Alpamayo 0.510, +0.219 [+0.123, +0.312], W41 / L11**, better on 7 of 8 segments. Weakness noted: shard 001 is 4 logs / 11 segments.

### 2026-09-30 Calibration against the field's easy baselines; rules; PAI zero-shot
- Ran the organisers' SimScale sample drivers (LTF, DiffusionDrive, GTRS-Dense) read-only [L-early]: shard 001 / 010 / mean: WA-JEPA 0.958 / 0.729 / 0.844; LTF 0.907 / 0.700 / 0.804; DiffusionDrive 0.853 / 0.690 / 0.772; GTRS 0.813 / 0.730 / 0.772; Alpamayo v0.3 0.759 / 0.510 / 0.635. Paired WA-JEPA minus samples on shard 010: LTF +0.029 [-0.059, +0.114], DD +0.039 [-0.049, +0.126], GTRS -0.001 [-0.086, +0.082]. Reading: WA-JEPA's gain is over our off-domain entry, not over the field. Per-scene oracle best-of-drivers headroom: WA-JEPA + LTF + GTRS 1.000 / 0.894. Fetched the real GTRS vocabulary object (sha256 e8c29cfc…) behind a git-lfs pointer.
- Rules check (Space, contestant guide, issues #123, #157, #182, #184, #188, #189, #191, model cards): WA-JEPA allowed (public weights and data); container contract met (5.4 GB image, 5.4 GB VRAM, read-only/no-network smoke test as uid 10001).
- Submission image `alpasim-jepa/wajepa:dev` (sha256:2a5b22e5…, 5.38 GB) verified in closed loop as an Apptainer sandbox of the Docker archive: 0.958, identical on all 100 scenes. Harness fixes: Apptainer overrides HOME; Slurm TMPDIR invisible in containers.
- **WA-JEPA zero-shot on PAI** (jobs 12996625/26, RTX PRO 6000 Blackwell) [PAI-local, n=40]: Alpamayo 0.668 (31/40); WA-JEPA crop 0.250 (21/40), -0.418 [-0.559, -0.267], W6 / L30; resize 0.301 (17/40), -0.368. Adapter healthy (0 fallbacks); the model does not transfer. Track split confirmed: PAI stays Alpamayo, nuPlan moves to this thread.
- Terms text read (Aman ran `terms show`): found and fixed a gap (no top-level licence/notice in the image) with `container/LICENSE` + `container/NOTICE`.
- New JEPA papers checked: AD-E2E-JEPA (arXiv 2609.34085; needs GT future observations as goals, unusable; 72.9 EPDMS zero-shot, 85.4 IL; repo README only) and Auto-JEPA (arXiv 2607.29031; 91.3 PDMS / 89.1 EPDMS, no code). Watch only.
- Plan agreed 09-30/10-01: this thread owns nuPlan; October slots PAI up to 2, nuPlan 1.

### 2026-10-01 GTRS-Dense judge for WA-JEPA plans
- Judge (`src/wajepa_challenge/judge.py`, GTRS-Dense ResNet reward vendored from the NVIDIA sample): append WA-JEPA's plan (8 to 40 poses) to the 16,384-path vocabulary, score s = log NC + log DAC + 3 log EP, switch if better by a margin.
- Round 1, global switching [L-early]: margin 0 switched 91-95% of plans, 0.773 (-0.185) on 001, +0.021 on 010; margin 2, 18-22% switched: -0.067 on 001, +0.077 [+0.029, +0.128] on 010. GTRS ignores the route, so its picks leave the recorded route.
- Round 2, radius-limited (GTRS may only pick paths within R m of WA-JEPA's at every 0.1 s pose): R1 m1 the only setting positive on both shards: 001 0.989 (99 passed) +0.032 [+0.010, +0.061] W5 / L0; 010 0.776 +0.047 [+0.008, +0.095] W7 / L6.
- Confirmed on untouched shard 005 (5 logs): WA-JEPA 0.944, judge 0.985, LTF 0.900, GTRS 0.886; judge vs WA-JEPA +0.041 [+0.001, +0.081], W6 / L2. Pooled 300 scenes: judge 0.917, WA-JEPA 0.877, LTF 0.836, GTRS 0.810; judge - WA-JEPA +0.040 [+0.019, +0.062], W18 / L8. Cost: Drive mean 0.39 s, GPU peak 5,716 MiB, 14-22% of plans corrected.
- Images: `wajepa:v1-4662979` (sha256:53019680…, 5.38 GB, plain WA-JEPA, clean commit, LICENSE/NOTICE) reproduced 0.958 bit for bit; `wajepa:v2-judge-6672747` (Docker dde3c672…, 5.64 GB, GTRS checkpoint + vocab sha-checked in `prepare.sh`) reproduced the native judge runs on all 100 scenes of 001 (0.989) and 010 (0.776), same correction counts (222 / 134).

### 2026-10-02 The local benchmark inverts the official ranking
- Warmup of the v2 judge image SUCCEEDED (see section 2).
- Leaderboard paste (80 entries) and calibration of drivers we had run locally against their official entries [L-early vs BOARD]:

| Driver | Local mean (shards) | BOARD scene | BOARD PCS |
|---|---|---|---|
| Alpamayo v0.3 | 0.759 (001), 0.510 (010) | 0.827 | 1284 |
| go_straight_with_delay_v2 (host) | constvel stand-in 0.578 | 0.799 | 1299 |
| SimScale DiffusionDrive (host) | 0.853, 0.690 | 0.772 | 1073 |
| SimScale GTRS (host/others) | 0.813, 0.730, 0.886 | 0.526-0.761 | 722-1014 |
| SimScale LTF (host) | 0.907, 0.700, 0.900 | 0.738 | 1019 |
| WA-JEPA (Lucifer AI's adapter) | ours 0.958, 0.729, 0.944 | 0.762 | 1022 |

- **Finding: every NAVSIM-trained model (LTF, DD, GTRS, WA-JEPA) is locally far above Alpamayo and officially below go-straight.** Public navtest flatters NAVSIM-tuned models (likely trained/selected on NAVSIM, e.g. `ltf_sim_navtest`). Decision: do not spend the slot on WA-JEPA as is; find local conditions that reproduce the official order before trusting local gains.
- Route-command audit (`src/analysis/route_audit.py`, 297 logged rollouts, 2,970 steps): the organisers' rule (first route waypoint ~40 m ahead) over-signals turns relative to NAVSIM's label (s = 20 m, +/-2 m): 551 steps (19%) it calls a turn where NAVSIM says straight. This corrected an earlier wrong note that it "almost always gives STRAIGHT".
- Route bridge (`route_bridge.py`: cubic Hermite ego to first waypoint, then NAVSIM's rule) and trajectory time scale (`timewarp.py`, the organisers' GTRS-sample warp in [1.0, 1.25]) built and unit-tested. Motivated by Lucifer AI's tag `routebridge-scale125` (0.879 / PCS 1553; inference from a tag only).
- **WA-JEPA ignores the drive command**: bridge changed nothing (identical on all 100 scenes); direct CPU test on real frames: plan endpoint at 4 s (42.16, 3.30) LEFT vs (42.13, 3.32) STRAIGHT vs (42.30, 3.30) RIGHT. Route snapping (`snap_plan_to_route`) built instead (keeps progress, blends onto the route by 25 m).
- Team view (28 of 84 entries): we were 8th of 28 teams (PCS 1290, v0.3). SymPhi `sp-1002a` jumped to 1809 (0.94), #1 overall.

### 2026-10-02/03 Snap + time warp; pivot to the public py123d checkpoint
- 300 scenes (001+010+005) [L-early/L-tune]: WA-JEPA 0.877; + judge 0.917; + judge + route snap 0.923 (snap vs judge +0.006 [-0.014, +0.026], neutral); route follower without a model 0.548; + time scale 1.25 (any combination) 0.60-0.67, collisions 0.16-0.21, dist to GT 6.6 m. Time scale dropped for WA-JEPA (speed runaway: the model replans from the warped speed).
- MTGS renderer took > 30 min to start on several nodes; launcher timeout raised to 3,600 s.
- **Public py123d_garage checkpoint** (`kesai-labs/py123d_garage_pretrained_checkpoints` @ 5516edd, `resnet34_v0.1.0/model_0014.pth`, Apache-2.0, "the reference starting point"): three official entries using it scored 0.848 / PCS ~1485 [BOARD] (host 014-nuplan-0014-v1 1484, YAX_NAM base0014-v1 1487, Lucifer 1485). Proposed options A (pivot to py123d + our levers), B (pure JEPA line), C (both). **Aman: C, do both.**
- py123d v0.1.1 locally (jobs 13121307-09, L40S, Drive 0.02 s) [L-tune]: 001 0.787, 010 0.656, 005 0.841. In the calibration table it is officially best (0.848) but near the local bottom, while NAVSIM-tuned models top the local table: **local scene score cannot rank model families**; only same-model comparisons are trusted (dist to GT ranked py123d first in both views, weak signal).
- Add-on launcher `src/garage_addons/entry.py` wraps py123d's `driver_service._make_plan` without modifying py123d.

### 2026-10-03 Storage incident 1 and log slimming
- 2026-10-02 ~22:17 UTC: the department fileset (5 TB quota) hit 100% (1.3 GB free); four of our runs died writing output. This folder held 296 GB, 173 GB of runs, almost all per-scene `rollout.asl` logs (~27 MB each, ~95% embedded camera JPEGs).
- Deleted superseded sandboxes and caches with per-item approval. Wrote `src/analysis/slim_asl.py`: keeps every log entry in order, empties only camera image bytes; verified per file (entry counts and kinds equal, non-image entries byte-identical; route audit md5-identical on slim vs original). **5,611 logs, 183.91 GB to 1.97 GB, 0 failed** (~93x). Sims slim their own logs afterwards.

### 2026-10-03/04 py123d add-ons: time warp, GTRS judge, determinism
- Time warp on py123d [L-tune, paired per shard]: 1.10 all plans: 001 +0.012, 010 -0.062 [-0.110, -0.019] (offroad 0.18 to 0.24), 005 +0.007, W72 / L16; 1.25: -0.118 / -0.124 / -0.080. **Straight-only (heading change < 10 deg over 4 s)**: 1.10: +0.012 [+0.007, +0.017] / -0.010 / +0.029 [+0.013, +0.049], W64 / L8; 1.15 straight-only worse.
- Slot plan (Aman, 10-03): slot 1 nuPlan = WA-JEPA + judge (`v4`); slot 2 PAI; slot 3 to the track with the better chance. Neutral tags.
- GTRS judge on py123d (`GARAGE_JUDGE=gtrs`, R 1 m, m 1) [L-tune, 300]: +0.016 [-0.000, +0.033], W22 / L39, rescues failing scenes (9 big wins / 1 big loss) and pays with many small progress losses. Judge + warp not additive, tripled collisions.
- Margin and warp-skip [L-tune]: m2 +0.027 [+0.011, +0.044] W20 / L14 (positive on every shard); m3 +0.025 [+0.011, +0.040] W13 / L6 big W8 / L0; **m2 + 1.10 straight-only warp skipped on judged plans +0.033 [+0.015, +0.052] W69 / L18**; m3 + skip +0.032 [+0.015, +0.049] W70 / L12. Skipping the warp on judged plans removes the extra collisions (0.010 to 0.003).
- **Determinism**: a rerun of py123d base on all 300 scenes on different nodes was bit-for-bit identical. All paired differences are add-on effects; the remaining noise is scene sampling (bootstrap) and transfer to the official score.
- ~8 settings tried on these 300 scenes, so held-out check on fresh part 013 (100 scenes, logs 2021-09-29 veh-28 and 2021-10-06 veh-52) [L-held]: base 0.686; judge m2 +0.046 [+0.017, +0.082]; m2 + skip +0.049 [+0.011, +0.092] W20 / L4; m3 + skip +0.049 [+0.011, +0.092]; warp alone +0.004. Picked **judge m3 R1 + 1.10 straight-only skip-judged** (same mean as m2, ~25% fewer swaps, fewer losses on tuning). Over 400 scenes: m2 + skip ~+0.037, m3 + skip ~+0.036.

### 2026-10-07 Single-shot rule; training cost; R2; storage incident 2
- Aman: the nuPlan entry may be our only official shot; "need every gain we can get (that is not noise...)". Rule from then: adopt only if positive on tuning AND on held-out never used for choosing; grow held-out (parts 007, 011 fetched).
- Licence recheck: py123d_garage GPL-3.0 briefly (08-24) then Apache-2.0 from v0.1.0; v0.1.1 Apache-2.0.
- Read the host's checkpoint README and configs: the host's 0.896 "0062" entries are most likely the nuPlan-only recipe at ~4x the epochs (posttrain script default `model_0062.pth`, preset `ltf_nuplan_trainval` max_epochs 63) [inference from names/configs, not confirmed]. Training became the biggest lever.
- Aman (10-07): keep the JEPA track alive. WA-JEPA judge margins 2 and 3 queued; route-conditioning pilot scoped (read-only study of WA-JEPA @ bec2966: command enters only via `ego_status`, Linear 8 to 512, broadcast to 8 trajectory tokens; planner = joint flow-matching predictor 12 blocks, width 512, ~170 M, over context 4,096 / future scene 8,192 / trajectory 8 tokens, 4 Euler steps; least-change design: `ego_status_dim` 8 to 10 with zero-init target-point columns; cache `context_scene` [4096, 512] exactly with a frozen encoder, train only trajectory-stream parameters).
- py123d add-on variants [L-tune]: judge command from the route bridge -0.003 vs best (rejected); judge radius 2 m +0.043 vs base (+0.011 [-0.007, +0.029] vs best).
- Queue fix: our fair share was the lowest in `edu`; allowing L40 and H100 (renderer arch list 8.9/9.0) and a 1 h 15 min limit let the scheduler backfill (23 sims in ~3 h).
- **py123d training cost measured** (10 logs): download 21.7 GB in 893 s (~24 MB/s unauthenticated); cache 390 s on 16 CPUs, 2.4 GB; 1,777 samples from 9 logs (~200/log), so full train+val (~1,310 logs) ~230-260k samples/epoch; one RTX A6000, batch 64, bf16, `max-autotune`: ~225 samples/s after an ~11 min compile, so ~20-30 min per full epoch. Schedule: cosine warm restarts T_0 = 1 epoch, T_mult = 2 (cycle ends 1, 3, 7, 15, 31, 63). Fixed: srun refusing after in-place edit (SLURM_TRES_PER_TASK), post-training hang (watchdog stop).
- **Held-out (013/007/011, 261) and R2** [L-held]: previous best (R1) +0.026 [+0.008, +0.045] W51 / L13; **judge m3 R2 + same warp +0.058 [+0.034, +0.082] W61 / L15** (tuning +0.043 [+0.020, +0.066]). R2 vs R1 held-out +0.032 [+0.011, +0.053], 11 big W / 1 big L. **Adopted R2.**
- WA-JEPA judge [L-tune / L-held]: m1 (the v4 image) tuning +0.040 [+0.020, +0.063], held-out 007/011 (161) +0.029 [+0.008, +0.053]; m2 tuning +0.043.
- Training pipeline queued (Aman approved): full 123D download, cache, py123d fine-tunes, WA-JEPA pilot. WA-JEPA pilot verified (`src/wajepa_route/verify.py`): cached-feature inference equals `predict_trajectory` exactly (max diff 0.0000 m); zero-init target-point encoder changes nothing; trainable 58.6 M of 788 M; gradients reach only those.
- **Storage incident 2 (my error)**: quota read from `df -h /insomnia001` (whole 1.7 PB filesystem, "490 TB free") instead of the 5 TB fileset; the 12-task download wrote ~197 GB and filled the quota (768 MB free), risking every writer on the fileset. Cancelled all jobs, deleted the partial download with Aman's approval (back to 199 GB free), recorded the rule (measure with `df -h /insomnia001/depts/edu/users/au2327`, keep >= 200 GB free). Full-dataset training no longer fit the fileset.

### 2026-10-08/09 Node-local pipeline; R3; fresh parts
- Aman: option 2, node-local disk only. Built jobs that download log batches to the node's `/local` (job TMPDIR, wiped at job end), cache, delete raw camera files, train, and write only logs and small checkpoints to the fileset. Verified py123d trains from the cache after camera files are deleted (814 samples from 4 logs listed from metadata + cache), so only ~0.25 GB/log compact cache stays.
- Node fault: ins082 (CUDA unknown error) excluded.
- WA-JEPA judge m2 vs m1: tuning +0.004, held-out -0.003; keep m1 (the v4 image). Judge held-out gain over plain WA-JEPA +0.025 [+0.006, +0.047] [L-held].
- py123d R3 [L-tune]: +0.061 [+0.035, +0.088] vs base; R3 - R2 +0.018 [+0.001, +0.036] W33 / L44.
- New `LOCAL_PART` mode in `sim_nuplan.sbatch`: build a track root on node-local disk with a downloaded asset part and drive only scenes not in any shared copy (no fileset space). Fixes: resumable download, bind of node-local root, 2 h limit.
- **Fresh parts 003 + 014 (193 never-used scenes)** [L-fresh]: R2 - base +0.075 [+0.048, +0.105] W38 / L9; **R3 - base +0.113 [+0.080, +0.149] W50 / L11**; R3 - R2 +0.039 [+0.014, +0.065]. **R3 adopted** (positive on both sets, never worse). Offroad on 014: 0.30 to 0.07.
- Node-local py123d pipeline works end to end (smoke 13286697: 30 logs cached in 30 min, 13 GB, one epoch of 10.9k samples). Script bugs fixed: `set -e` + `pipefail` on a `test && echo` loop; first batch had no val log; watchdog kill under `set -e`; `ls | head` under pipefail.
- Radius 5 / unlimited [L-tune]: R5 +0.010 [-0.009, +0.030] vs R3 (n.s.); unlimited +0.037 [+0.002, +0.072] but 26 big W / 17 big L. GTRS path used 11% (R1), 19% (R2), 23% (R3), 25% (R5), 27% (unlimited). R3 kept (unlimited hands unconstrained manoeuvres to a NAVSIM-family planner).
- Driver integration for the WA-JEPA route checkpoint; `target_point_py123d(route)` reproduces py123d_garage's AlpaSim target point **exactly (0.0 m on 205 random routes**, `src/analysis/test_target_point.py`).
- R6000 (RTX PRO 6000 Blackwell) nodes ins046/047 allowed; they have 14 TB `/local`.

### 2026-10-09/10 py123d fine-tune A
- **Fine-tune A** (job 13287171, R6000 ins046): 430 logs (362 train + 68 val, spread over the index), cached on `/local` in 5.3 h (133 GB cache), camera files deleted; from public `model_0014.pth`, nuPlan-only preset, 15 epochs (cosine restarts 1+2+4+8), batch 64, `max-autotune`, ~108k samples/epoch (1,693 steps), **~485 samples/s on one RTX PRO 6000**, ~4 min/epoch, **25,395 steps in 1 h 8 min**. Kept epochs 3, 7, 15.
- Fine-tune A plain vs public [L-tune]: epoch 15 **+0.059 [+0.034, +0.084] W72 / L34** (per shard +0.054 / +0.063 / +0.062), epoch 7 +0.051; offroad 0.107 to 0.040. No leakage (nuPlan train/val vs navtest = nuPlan test). Fixed: exported `sensor_rig_0.yaml` had no cameras after deletion; `GARAGE_RIG` passes the public rig (an image of a fine-tune must ship the public rig).
- Across sets, vs public base: public + R3 +0.061 / +0.063 / +0.113 (tune / held / fresh); FT A plain +0.059 [+0.034, +0.084] / +0.047 [+0.021, +0.075] / +0.036 [+0.014, +0.059]; FT A + R3 +0.073 [+0.046, +0.101] / +0.079 [+0.044, +0.114] / fresh +0.114 [+0.080, +0.152] (after an ECC rerun).
- Hardware fault: 26 of 100 rollouts of one run failed with "CUDA error: uncorrectable ECC error" on ins058 (scored 0); rerun, node excluded; `report.py` now warns on any run with > 2 infrastructure failures; scan of all runs found no others.
- FT A + R3 vs public + R3: all 754 scenes **+0.011 [-0.002, +0.025]**, W116 / L95, big W20 / L20, P(> 0) = 0.91. **Lead candidate: FT A + R3** (the fine-tune alone does not depend on the NAVSIM-trained judge transferring).
- WA-JEPA full pilot (13287532) hung in encoding after 5.4 h of data (201 GB features); fixed with DataLoader `timeout=300`, per-batch limits and a data deadline.
- **WA-JEPA route pilot round 1** (13303410, A6000) [OL, 1,091 val samples, 160 turns]: ~9.8k train samples, 1,726 steps (3 epochs), lr 1e-4, ~11 samples/s. Released ADE 0.654 / FDE 1.831 / lateral 4 s 0.323 (turns 0.488 / 1.203 / 0.757); route fine-tune 0.676 / 1.890 / 0.326 (turns 0.577 / 1.432 / 0.842); control (no route) 0.682 / 1.910 / 0.331 (turns 0.589 / 1.484 / 0.863). Fine-tuning degrades the released model (overfitting ~10k samples; it was already trained on navtrain from these logs); the route input helps only relative to the control.
- HF anonymous downloads throttled to ~1 MB/s; **Aman approved** using the AlpaSim HF token file in place (path only, never on a command line): ~12.5 MB/s per stream with `HF_XET_HIGH_PERFORMANCE=1`; 3 parallel downloads per batch.

### 2026-10-11 Pilot round 2 negative; A2; soup; candidate Q built
- **WA-JEPA pilot round 2** (13310920) [OL]: 4.9k samples, 878 steps per run; released 0.681 / 1.892 / 0.328 (turns 0.503 / 1.215 / 0.768); target-point encoder only lr 1e-4: 0.699 / 1.976 / 0.375; route + trajectory stream lr 1e-5: 0.697 / 1.919 / 0.331; control lr 1e-5: 0.691 / 1.909 / 0.330. Route input does not lower training loss (5.9e-5 both). **Decision: WA-JEPA fine-tuning paused** (6 runs, none beats released weights open-loop, so no closed-loop test warranted). Round 1 vs 2 released numbers differ because the val sample sets differ.
- **Fine-tune A2** (13320641, A6000 ins094): from A epoch 15, disjoint third (`OFFSET=1`, 271 train + 29 val logs, fetched with the token in 5.3 h), 15 epochs, 72.8k samples/epoch, 17,055 steps. A2 plain - A plain over 561 tuning + held-out scenes +0.011 [+0.001, +0.023] W90 / L56; A2 + R3 - A + R3 -0.009 [-0.020, +0.002]. More data helps the plain model slightly; with the recipe, A stays ahead. Fresh-part A2 runs cancelled (download did not finish; could not change the choice).
- Bug: an inline comment inside a line-continued `hf download` command cut its arguments; fixed and all job scripts scanned.
- **Model soup** (A + A2, 666 float tensors averaged, integer counters from A): soup + R3 - A + R3 +0.001 [-0.011, +0.014]. Rejected.
- **Candidate Q = fine-tune A (epoch 15) + R3 recipe.** Image `local/q:1` (12.8 GB, image id ae4b8656b624): build-time sha256 of model.pth 8691cc01…, config a0b17835…, public rig 453ddf94…, GTRS ckpt 8dad0395…, vocab e8c29cfc…. Apptainer could not read Docker Desktop's gzipped export; built the sandbox on node-local disk instead. **Verified in closed loop (13334978-80): 001 100/100 and 010 100/100 scenes identical** (L40S); 005 85/100 identical with the same mean to 4 decimals (H100 vs L40S floating point, 15 tiny differences, max 0.027).

### 2026-10-12 Failure analysis; stall rescue
- Qwen-Drive-1.0 (arXiv 2609.00111, Qwen3.5-4B + ~1.1B planning expert) checked: its own AlpaSim closed-loop table (Alpamayo-1.5 0.45, SimWAM-IL 0.30, Qwen-Drive SFT 0.27, RL 0.37) and Alpamayo already below py123d officially; not pursued. Told the PAI agent.
- **Where Q loses** [754 local scenes, mean 0.809]: passed-but-low-progress scenes cost 0.100 (126 scenes, mean 0.40; human drove only 10-20 m, typically from rest) **more than** zero-score failures 0.089 (67: offroad 34, corridor 13, collision 11, route sanity issues 8, infra 1). py123d stays nearly stopped where the human moved off; the radius-limited judge cannot replace a stationary plan with a moving one.
- **Stall rescue** (judge.py, opt-in): if the chosen 4 s trajectory ends < `stall_m` from the ego, use the best GTRS vocabulary path that moves >= 3 m with NC and DAC probabilities > 0.9 when its score beats the plan's by `stall_margin`.
  - 1 m, margin 1: tuning +0.024 [+0.009, +0.041] W12 / L4 (1 new offroad, 1 new collision); held-out +0.031 [+0.017, +0.048] W13 / L0; fresh +0.035 [+0.017, +0.054] W10 / L0; **all 754 +0.030 [+0.020, +0.039] W35 / L4. Adopted.** Image `local/q:2` (3f315f660f72, git 7bdfd99) verified 100/100 + 100/100 identical.
  - Off-road guard from DAC rejected on logs (low-DAC unsubstituted decisions in 35 passing vs 7 failing scenes).
  - Threshold 3 m vs 1 m: tuning +0.013 [+0.005, +0.022] W12 / L1; held-out +0.013 [+0.002, +0.025] W12 / L1; fresh +0.012 [+0.005, +0.022] W7 / L0; **all 754 +0.013 [+0.008, +0.019] W31 / L2. Adopted.** Image `local/q:3` (0d13aceb9285, 12.79 GB) verified 100/100 + 100/100 identical (means 0.9024, 0.7813), 42 rescues logged.
- Storage cleanup (per-item approval): 41 dead run folders, timing-test checkpoints, rejected soup, 12-log cache.

### 2026-10-18 Stall 5 m / 8 m; dedupe; tag register
- 5 m vs 3 m: tuning +0.023 [+0.013, +0.034] W19 / L1; held-out +0.011 [-0.000, +0.023] W15 / L2 (1 new collision, 1 corridor); fresh 003 +0.012; fresh 014 -0.002 [-0.008, +0.003]; held-out + fresh (454) +0.008 [+0.002, +0.016] with 3 new zero-score scenes vs 1 fixed. **Kept 3 m**: the gain shrinks off the tuning set and trades progress for zeros (a knob tuned past what generalises). 8 m vs 5 m: -0.000, 2 new zeros; rejected.
- Means over 754 [local]: Q without stall 0.809, Q + stall 3 m (q:3) 0.852 (+0.042 [+0.032, +0.054], W57 / L3).
- Storage dedupe with the PAI agent (Aman approved): sha256 of every file of the shared nuPlan metadata on both sides (85,035 + 1,491 files) identical; our copies replaced by symlinks. My error: one run was still copying the metadata when the links replaced it (cancelled); this exposed that copying 85k small files from GPFS took > 2 h (the real cause of earlier fresh-part timeouts). Fixed with symlinks + an extra read-only bind; link check bit-identical.
- Tag clash resolved: nuPlan keeps v6 (Q), PAI takes v5 / v7.

### 2026-10-20 Fine-tune A31
- A31 (13569405, A6000 ins094, 8.9 h: data 4.3 h, 108,414 samples; training 4.5 h, 31 epochs / 52,483 steps). With the Q recipe vs q:3 [L-tune]: epoch 31 -0.003 [-0.016, +0.011] W32 / L33; epoch 15 +0.004 (reproducibility check of A's schedule, sound). Longer training gives no gain; held-out/fresh not spent.

### 2026-10-21 v6 submitted and failed
- Decision brief: q:3 vs public py123d over 754 [local]: **+0.128 [+0.108, +0.149], W212 / L52** (tuning +0.110, held-out +0.123, fresh +0.162); means 0.852 vs 0.724; offroad 105 to 36, collisions 11 to 12, corridor 15 to 13; at-fault km per collision 1.64 to 1.74 locally. I projected ~0.91-0.93 official scene score and ~2nd among eligible teams (P(#1 eligible) ~15-25%).
- Aman pushed v6 (digest above), warmup succeeded, official submitted.
- **BOARD: scene 0.782, PCS 1131 [1076-1186], rank 48 (interval 46-60), 0.324 km, GT 1.766 m**: below v0.3 (0.827 / 1298) and the public checkpoint (0.848 / ~1485). Run valid (verified digest, 1,000/1,000, 1,189 s).
- Cause analysis: the local gain was dominated by NAVSIM-family components (GTRS-Dense critic trained on navhard, navtest-tuned warp, stall rescue that defers to the critic), which this ledger had already shown to be flattered by navtest (10-02). Dist to GT 1.77 vs 0.6-0.75 for py123d entries points the same way. Not separable with one run.
- Hard rule recorded: local navtest gains from anything NAVSIM-trained or navtest-tuned do not predict the official score.
- Time-warp breakdown given to the PAI agent [local, plain public py123d +/- warp]: 1.10 all plans -0.014 (stop-go scenes +0.034 W54 / L5; moving urban -0.058, corner cutting); straight-only +0.009 W80 / L11; 1.25 -0.108 (22 passes to at-fault collisions). Precision check: our fine-tunes were bf16-mixed with fp32 master weights (safe).
- Aman: nuPlan out of the picture, focus on PAI.

### 2026-10-23 nuPlan back on; py123d v0.2
- Organisers extended nuPlan to Nov 16 AoE. Aman: "nuplan is back on"; PAI FlashDrive work I had started here (code `pai_flashdrive/`, open-loop on A6000: 11.6 GB, 884 ms/plan non-streaming, ADE 1.09 m) handed to the PAI agent.
- py123d_garage v0.2.0/v0.2.2: four 68M camera-only Latent TransFuser variants (base-joint32/64, base-waypoints, streaming-joint64), 3 seeds each, pretrain / midtrain / posttrain; flow-matching planner (64 waypoints over 6.4 s + actions + 64 m path); front camera only on nuPlan (current + 1 s earlier); up to 3 route target points at 40 / 60 / 80 m; trained on PAI AV + NuRec + nuPlan train/val (not navtest). Model card joint64: local nuPlan (1,485 navtest scenes) 91.4 +/- 1.0, 0.747 km/incident.
- Board 10-23 (147 entries): SymPhi 1932, host 093 1918, host 092 1885, nuVAIL 1853.
- **Candidate N1** `local/n:1` (0a06ba20a19c, 12.6 GB): py123d's v0.2.2 submission Dockerfile with the released joint64 posttrain `model_0.pth` (sha256 d7113ef3…). New `DRIVER=garage2` runs py123d v0.2.2 natively for fast A/B.
- N1 image [L-tune 300]: 0.908 vs public 0014 0.761, +0.147 [+0.114, +0.182] W96 / L17; vs the v6 recipe +0.037 [+0.013, +0.061]. garage2 seed 0 vs image: 175/200 identical (GPU types).
- Published per-seed results [HOST-PUB, 1,485]: joint64 s0 0.917, s1 0.904, s2 0.923; joint32 0.908 / 0.904 / 0.898; waypoints 0.895 / 0.902 / 0.892; streaming-joint64 0.909 / 0.898 / 0.903.
- **Every v0.2.0 lever tried on joint64 seed 0 failed held-out** (garage2, paired vs seed 0):
  - 3-seed ensemble (plans averaged): tuning +0.007 [-0.006, +0.020]; held-out 007+011 -0.019 [-0.045, +0.006]. Dropped.
  - nuPlan-only fine-tune ftN (13648035, A6000 ins093, 3.5 h; 400 logs, 362 train + 38 val, 497,784 samples, 7 epochs / 54,439 steps, ~402 samples/s, `compile_mode=default`; earlier attempts died on a caching-allocator assert with `expandable_segments` + CUDA graphs, a segfault in `cudagraph_trees` replay, and my `grep "Cached"` script bug): alone -0.012 [-0.030, +0.004]; WiSE 0.5 +0.000; WiSE 0.3 +0.001 [L-tune]. Dropped.
  - Replan 10 Hz / 5 Hz: -0.006 / -0.000; later verified a no-op (control step fixed at 500 ms), and the difference was GPU-type noise (~0.006 noise floor).
  - MPC gains: lat_position_weight 2.0 -0.000; idx_start_penalty 15 tuning +0.004 [+0.002, +0.006] but held-out -0.014 [-0.026, -0.002] with 4 new zeros; idx 19 tuning +0.012 [+0.006, +0.020], held-out -0.010 [-0.024, +0.003], same 4 new zeros.
  - Policy inference options: driven_output actions +0.002, waypoints_on_path -0.007, actions_on_path -0.004, 16 inference steps -0.002 [-0.004, -0.000].
  - Seeds / target points: seed 2 alone +0.003; seed 0+2 ensemble tuning +0.010 [+0.002, +0.019] then held-out -0.009 [-0.024, +0.005] with 4 new zeros; no target points -0.017; 40 m target only +0.000.
  - Averaged flow samples (noise temperature 1.0 / 0.5 x 8 draws): -0.016 / -0.015.
  - extrapolate_route: -0.003.
- Board 10-25 (154 entries): nuVAIL 2016 (0.974, 1.43 km), SymPhi 2001, host 093 1979. Research sweep: no public method from the leaders; no further nuPlan-applicable releases before Nov 16.
- **Where seed 0 loses** [561 L-tune + L-held, mean 0.900]: zeros 5.5 points (offroad 18, collision 2, corridor 2, plus 8 public route-foldback scenes and 1 corrupt asset); partial progress 4.5 points (68 scenes), of which **17 scenes stall: the ego never starts while the logged car covers 6-14 m**, persistent across every variant.
- **Stall diagnosis** from plan logs (13664147-48, all 17 reproduce): ego starts at rest; in 11 of 17 the policy plans "wait 1.7-4.0 s, then go" at every replan; the MPC tracks only the next 2.5 s (all waiting), so the ego never moves: a receding-horizon "always later" start. In 6 the plan itself stays stopped.
- **Start-now add-on** (`src/g2_addons/entry.py`, wraps `GarageDriver._plan`): when stopped (< 0.5 m/s) and the last K plans were wait-then-go, drop the waiting prefix of the next one. Results vs seed 0:

| | L-tune 300 | L-held 261 | L-fresh 193 | all 754 | new zeros | any-collision |
|---|---|---|---|---|---|---|
| K=3 | +0.012 [+0.005, +0.020] | +0.013 [+0.005, +0.022] W13 / L3 | +0.022 [+0.009, +0.038] W9 / L0 | **+0.015 [+0.009, +0.021]** | 0 | 19 to 13 |
| K=1 | +0.013 [+0.003, +0.024] | +0.022 [+0.008, +0.038] | +0.031 [+0.015, +0.049] | +0.021 [+0.013, +0.029] | 2 at-fault collisions | 19 to 12 |

- **Adopted K=3** (CI > 0 on all three sets, no new zeros, rule logic, no NAVSIM component). Image `local/n2:1` (sha256:5ea4001e…, 12.6 GB) verified on the cluster: 16 rescues = garage2 K=3; vs garage2 K=3 -0.001 (280/300 identical, GPU-type noise); vs seed 0 +0.011 [+0.003, +0.020]. Tag v8 (PAI's final is v7).
- Remaining zeros with K=3 (22 of 561): a log-replay control (ego forced on the log) scores 1.0 on 17 and 0 on 5; the 5 are unavoidable public-map artifacts; the 17 are real model errors (13 offroad, 2 at-fault collisions, 2 corridor), typically a 0.2-1 m drift to the outside at a bend or lane split.

### 2026-10-26/28 Closed-loop data collection
- Aman: "go ahead with the closed-loop build". Built `src/g2_addons/collect.py` (records the policy's exact inputs, ego state and the logged ego trajectory per plan; DART-style lateral perturbations on served plans so states leave the log), `src/closed_loop/labels.py` (recovery labels in py123d's format: project ego on the log, ease lateral and heading error to 0 over max(8 m, 2 s x speed)), `src/closed_loop/train_decoder.py` + `cluster/cl_train.sbatch` (freeze all but `planning_decoder`, py123d's own flow loss).
- Fileset small-file slowdown (~10x; MTGS UnifiedDataset scan of the 85k-file trajdata cache went from 4.5 min to > 40 min, 4 jobs timed out): fixed by storing the two public cache archives (2.17 GB `nuplan_test.tar.gz`, sha 3a87fffa…; `configs.tar.gz`, sha 9c93aa6a…) and extracting them to node-local disk in ~35 s (control run 2.6 min total, identical scores).
- Collection: 687 scenes from the 7 public parts no eval set used (002, 004, 006, 008, 009, 012, 015), start-now K=3, perturbation p 0.3, M 1.0 m x 3 plans.
- 10-28: paused on Aman's request (all GPUs to PAI until Oct 31).

### 2026-11-04/07 Resume; PCS proxy; closed-loop decoder fine-tuning (negative)
- Read `../LESSONS_FOR_AGENTS.md` (PAI v7 beat v5 on every visible metric yet lost PCS).
- Board 11-04 (198 entries): nuVAIL 2124 (0.982), SymPhi 2135, Lucifer 2127, host 093 2119. v8 not yet submitted (CLI session expired).
- **Local PCS proxy** (organisers' `e2e_challenge/local_evaluation/evaluate.py`, Drive-IRT @ 82ddd5a, zoib; 20 of our policies x 552 scenes) [PROXY]: start-now K=3 3.93, K=1 3.99, idx 19 4.00, idx 15 3.93, ens02 3.84, ens3 3.76, seed 0 3.75, WA-JEPA + judge 2.62, v6-era stacks 1.0-2.0, public 0014 0.66. K=3 - seed 0 over 3 fit seeds +0.18 / +0.10 / +0.20 (posterior std ~0.2). Caveat stated: population is ours only.
- Evaluation-condition check: local simulator 2023534 vs competition e121e59 differ only in scoring (corridor fix); seed 0 had 2 corridor zeros in 552, both real.
- Consolidation (Aman approved): PAI closed; its cluster folder deleted; what we used was moved here (nuPlan metadata, shard-001 assets, simulator sandbox, simulator code `ext/alpasim_sim`, HF token mode 600 with unchanged sha). Smoke sim from new paths identical.
- **Decoder round 1** (13798308, A6000, 21 min incl. env build): 3,982 usable records (2,888 skipped: label would need > 3.4 s extrapolation), 694 off-log; train 3,538 / val 444 (77 scenes, split by scene); 4 epochs, 444 steps, lr 2e-5 one-cycle, backbone and other heads frozen. Validity: loss 0.335 to 0.218; held-out sampled-waypoint L1 2.914 to 2.652 m (off-log 4.434 to 3.805 m, n=75); decoder moved 0.0005 relative L2. Closed loop vs v8 [L-tune]: **-0.013 [-0.033, +0.005]**, W29 / L16, 9 new zeros (6 offroad, 3 at-fault collisions). Tested properly, no gain. Likely cause: log-timed labels make the decoder more assertive.
- Exchange with jepa-nureasoning (11-05/06): our 5 s distance bias of released seed 0 vs log (part 002 recordings, n=96): mean -1.49 m, median -0.66 m; theirs on real Motional images (1,000 val key frames): mean +0.38 m, at rest +2.61 m (goes too early). Their decoder fine-tune on real images fixed their bias but has the opposite sign of ours, so not transferable.
- **Decoder round 2, lateral-only labels** (Aman: "i still think we should go for it"): labels keep the policy's own speed profile, correct only geometry. Env build had become 2,533-3,198 s from the GPFS slowdown; built `cluster/pack_g2env.sbatch` (packed env 7.4 GB tar) so jobs extract it in 142 s. Training 15 min each: `r2lat` (lr 2e-5) held-out cross-track 0.594 to 0.607 m (no offline gain); `r2lat_hi` (lr 1e-4) 0.594 to 0.571 m (-4%), off-log 1.402 to 1.222 m (-13%, n=72). Closed loop vs v8 on L40S [L-tune]: A/A v8 L40S vs original -0.0009 [-0.0029, +0.0001] (280/300 identical); `r2lat` **-0.016 [-0.028, -0.006]**, 4 new zeros; `r2lat_hi` **-0.026 [-0.043, -0.010]**, 8 new zeros. Worse with more dose.
- **Self-distillation control** `r2self_hi` (same recipe, label = own served plan): -0.003 [-0.018, +0.012], zeros 16 to 15; `r2lat_hi` vs control -0.023 [-0.042, -0.004]: the lateral labels themselves cause the offroads. Why: labels sit ~0.1-0.2 m right of the model's own line even on straight road (n=156; cause unresolved: human line or reference-point/frame offset). **Verdict: closed-loop decoder fine-tuning, 3 label variants + control, tested properly, no gain.**
- **Rule tests on top of v8** (Aman: "run the two quick rule tests"; pre-specified single settings; 561 paired scenes, 90% CI half-width ~0.007): idx_start_penalty 19 + K=3 tuning +0.0066 [-0.0001, +0.0143], held-out **-0.0124 [-0.0266, -0.0002]** with the same 4 deterministic new zeros as before; straight-road warp 1.10 ported to the 64-pose v0.2 plan: combined -0.0053 [-0.0129, +0.0013], 5 new zeros. PCS proxy refit with 22 subjects: both proxy-positive but within fit noise. Neither adopted.

### 2026-11-08 v8 submitted
- Pre-push checks on the Mac image (entry.py md5 1252015d… = repo, `G2_START_K=3`, checkpoint sha d7113ef3…, NOTICE present). `limits`: 3 official, 2 nuplan-warmups left; `v8` absent from the registry.
- v8 BOARD result: **PCS 1854 [1738, 1969], mean 0.9086, 0.682 km, GT 0.836 m; entry rank 33 [25-38], team rank 18 of 58** (1,000/1,000 valid, 1,145 s).
- **Board-side control**: four other teams' unchanged joint64 seed 0 entries scored mean 0.9205, 0.834 km, GT ~0.67, PCS 2074-2083. v8 is about -225 PCS below its own base. Locally (552) the same pair went the other way (+0.012). Cause not established (start-now misfiring on hidden scenes vs image difference).

### 2026-11-09 Seed 2 (N3) and the discovery of W1
- Warmups are not scored, so the "warmup diagnostic" I had suggested does not exist; any board evidence costs an official slot.
- Seed choice from host data [HOST-PUB, 1,475 scenes excluding foldbacks]: joint64 seed 2 +0.0062 [-0.0015, +0.0139] W155 / L88 vs seed 0 (15 new / 15 fixed zeros); every other checkpoint worse (-0.007 to -0.024). PROXY on host population: seed 2 first in all fits (3.93-3.97 vs seed 0 3.34-3.40). **Proxy validity check failed**: with host + our variants, v8 still ranked above seed 0 (+0.27 to +0.30), opposite of the board (-225). Image `local/n3:1` (31b8fd62e222) built, never submitted.
- Eligibility read: released public weights are eligible as written; the report would have to say plainly it is the host's released checkpoint.
- Board map 11-08 from mean to PCS near the top: 0.9205 to ~2080, 0.9242 to 2100, 0.9387 to 2141, 0.9405 to 2171; first place SymPhi 2198 (0.971).
- **Aman pointed at the host's rank-4 entry; I had missed it**: 093-nuplan-v1 (PCS 2181 [2063, 2298] on 11-08; 0.9437 / 0.981 km / 0.590 m) is the **released ltf-base-waypoints-68M posttrain seed 1** (its HF README says "the seed on the leaderboard"; incident and GT distance match to 3 decimals). Likewise joint32 seed 2 = host 120-nuplan-v1. So a public, prize-eligible checkpoint is ~100 PCS above joint64 seed 0 on the board although it is worse locally on the host's own 1,485 scenes. Local scores (and the proxy) cannot rank released checkpoints; the board can.
- Image `local/w1:1` (db5833d60444): waypoints posttrain `model_1.pth` (sha256 ae1619d5…, = HF LFS oid) + config (6a2f472d…) from HF @ 56edbe90; strict load, 825 tensors, 67.1 M parameters.

### 2026-11-10 New releases; W1 verified; failure census; shadow mode
- Checked Aman's finds: Alpamayo 2 Edge (2.45B + 0.2B action expert; needs six NVIDIA cameras and -0.1 s frames, off-rig; OpenMDW licence vs Apache terms unresolved), FlashDrive on Alpamayo 2 Super (34B, unsupported; speed does not raise the score), SimForge Pilot-4B v1.5 (gated, off-rig, p95 1.62 s latency on A100). None usable.
- **W1 harness check** (13852543/45, garage2, L40S) vs the host's published W1 per-scene results on shards 001 + 013 (200 scenes): **182 identical, mean 0.9044 vs 0.9044, diff -0.0000 [-0.0001, +0.0000], no zero flips**. Our driver reproduces the host's 093 run. Bad nodes excluded (ins038, ins057, ins059, ins061 exit 0:53 with no log; ins063 CUDA unknown error).
- Videos of 15 W1 failure scenes (all reproduce, 14 exact): `analysis/w1_videos/`, frame grids `analysis/w1_*.jpg`, list of 241 losing scenes `analysis/w1_failures_public1485.csv`.
- **W1 failure census** [HOST-PUB, 1,485, mean 0.902]: low progress 179 scenes = 58% of lost score (63 scenes < 2 m driven, GT median 9.4 m, 24 of 63 rear-ended by log-replayed followers); offroad 53 (36%; 34 of 53 driven clean by another released checkpoint); at-fault collision 8; corridor 1. Video patterns: waits at a light that looks red in every rendered frame (frozen reconstructed light suspected, not verified), never moves on an empty street, stays behind a stopped car, drifts onto a median curb.
- 3-seed waypoints ensemble vs W1 [local, all 6 shards, 557]: +0.0074 [-0.0047, +0.0202], W34 / L48, 4 new zeros / 3 fixed, signs flip across shards; Drive 0.136 s vs 0.050 s. No gain shown (underpowered; failures traded).
- **Shadow driver** `src/g2_shadow/entry.py` (wraps `TransfuserPolicy.forward` and `GarageDriver._plan`; plans unchanged, verified scores = plain W1): logs per plan speed, 64 poses, route ahead, the model's own detected boxes (class, speed, heading), predicted drivable probability at each pose and 1 m to each side, argmax BEV. Runs on 6 shards (552 scenes): outcomes clean 469, low 38, stuck 23, offroad 17, collision 3, corridor 2. Analysis `src/analysis/shadow_triggers.py`.
- **Fix 2, off-road guard from the predicted road: not viable** (best: catches 2-3 of 17 offroad scenes; the map does not resolve the sub-metre curb drift; plan poses read 0.97-1.0 drivable at centre while going off-road).
- **Fix 1, stall-nudge trigger**: slow (< 0.5 m/s), plan moves < 1 m in 2 s, no box of any class within 25 m along the route corridor (|lat| < 2 m), no crossing moving vehicle within 30 m, no static object within 15 m ahead / 8 m lateral, for K = 3 consecutive plans.
- **Bug found while building (caught before use)**: the driver's route starts ~40 m ahead of the ego, so the corridor must start at the ego. Corrected counts (K=3): **fires in 14/23 stuck, 4/38 low, 1/469 clean, 0 failing scenes** (v8's start-now trigger on the same logs: 11/23 stuck and 27/469 clean).
- `src/g2_nudge/entry.py`: A = drop the wait (start-now action on wait-then-go plans); B = A + gentle creep along ego to route for stay-stopped plans (1.0 m/s^2 up to 4 m/s, only if near-straight).
- GPU mistake: A6000 runs queued for the MTGS renderer, which needs sm 8.9/9.0; cancelled before start.
- **Firing-set design**: until the nudge first acts, a scene drives bit for bit as plain W1, so only scenes where the trigger fires can change. Ran base / A / B on the 40 loose-firing scenes in one job on one GPU (`cluster/sim_nuplan_multi.sbatch`), pooled effect = sum of differences / 552.
- NuRec infrastructure: renderer image build OOM at 16 GB, then a 6 h timeout unpacking on GPFS; fixed by pulling on node-local disk and unpacking per job; CRLF line endings in the scene id file; `APPTAINER_TMPDIR` must exist; NRE `ptx_cache` bind target missing in a fresh unpack. Smoke passed on R6000 ins046: ~4 min per scene, driver peak 1.2 GB. Full 4 drivers x 441 scenes = ~118 GPU-h estimated, too slow; switched NuRec to the firing-set design too (base pass once per model with shadow logs, candidates only on firing scenes).

### 2026-11-11 Stall nudge: nuPlan positive, NuRec not clean
- Tuning firing set (job 13857369, H100, 40 scenes) [L-tune]: trigger reached K=3 in exactly the 19 scenes shadow mode predicted. **A +0.178 [+0.082, +0.286] on the 40, W11 / L0, no new zeros (pooled +0.0129 over 552); B +0.226 [+0.120, +0.340], W14 / L0 (pooled +0.0164).**
- **Fresh nuPlan, 6 parts never used for the design (600 scenes)** [L-fresh], base/A/B paired on one GPU per part: **A +0.0118 [+0.0051, +0.0198], W14 / L0, no new zeros; B +0.0134 [+0.0063, +0.0220], W16 / L0.** Per part A/B: 002 +0.0221, 004 +0.0179, 006 +0.0208, 008 A 0 / B +0.0098 (creep), 009 +0.0100, 012 +0.0001. Gain confirmed on held-out nuPlan.
- **NuRec**: base pass (W1 and joint64 s0, 12 chunks of ~37 scenes each, R6000 ins046/047): chunk 0 W1 0.707 (30/36 passed), j64s0 0.725 (32/36). Triggers fire far more (nudge exact 9/36 on W1 vs 19/552 on nuPlan): NuRec scenes are ~20 s (40 plans) vs ~5 s, with more mid-scene stops (18% of plans stopped vs 9%). **NuRec is not bit-repeatable**: W1 rerun vs original -0.0016 [-0.0056, +0.0012], 8 of 14 scenes differ; candidates always paired with a base rerun.
- Chunk 0 nudge set (14) [NuRec]: A +0.0364 [+0.0009, +0.1027] W5 / L3; **B -0.0924 [-0.311, +0.092], 2 new zeros** (creep during a mid-scene wait: one corridor exit, one at-fault collision). Variant Bs (creep only before the first move): chunk 0 +0.0443, but group 0 caused an **at-fault front collision** (model's boxes missed the car ahead). **B and Bs dropped.**
- Node fault ins046 17:46:20-17:46:44 killed all jobs there (also the jepa-nureasoning thread's); resubmitted.
- A across chunk 0 + groups 0-2 (110 firing scenes) split by whether A acted: acted (54) +0.0674 [+0.0245, +0.1230] W27 / L2; never acted (56) +0.0002 (= rerun noise).
- **A complete on NuRec (167 firing-set scenes, chunks 0-11)**: acted (79) +0.0461 [-0.0117, +0.1041], W39 / L8, new zeros 2 / fixed 2, **new at-fault collisions 3, removed 1**; never acted (88, noise) -0.0112, new at-fault 1. Over all 440: +0.0060 per scene. Two clean scenes got at-fault front collisions ~2 s after drop_wait. **Verdict: no gain shown on NuRec; A adds at-fault collisions after acting (v8's board failure mode at a lower rate). Not a safe candidate as is.**
- Aman: K=2 not to be tested; GPU-count cap lifted through the deadline. Aman's call (11-11): submit A anyway ("go out on a limb", "we anyways have nothing"), keep the last slot for plain W1.
- Image `local/w1n:1` (sha256:da1fe936…, 12.8 GB): FROM w1:1 + g2_nudge, MODE A, K 3, latch on, creep-from-rest off; entry.py md5 93677e79… = repo = cluster copy.
- **v8 on NuRec (188 start-now firing scenes)**: -0.0009 [-0.024, +0.019], W62 / L21, 4 new zeros (3 at-fault collisions on scenes j64s0 scores 1.0), 0 fixed.
- **NuRec vs board calibration**: W1 vs j64s0: board W1 better; local nuPlan said j64s0 (wrong); NuRec base pass 440 W1 0.685 vs 0.668 (right). v8 vs j64s0: board worse; local nuPlan +0.012 (wrong); NuRec flat mean, +3 at-fault (right on incidents). W1 km per at-fault incident: board 0.981, local nuPlan fresh 1.195 (600), NuRec 1.088 (440); mean board 0.944, nuPlan 0.920, NuRec 0.685.

### 2026-11-12 v9 submitted and failed the same way
- **v9 image check** (imagep from the archive, H100 part 002 and L40 part 004): **100/100 and 100/100 scenes identical** to the tested garage2 A runs; driver log `mode=A K=3 ...`. Packaging slip ruled out.
- Fresh part 015 (91) [L-fresh]: A +0.0231 [+0.000, +0.054] W3 / L0.
- Rule #232 read: final runs use each team's highest-scoring submission.
- Board 11-12 (240 entries, 60 teams): all PCS refit (-112..+102); host W1 2181 to 2247; top three entries at exactly 2279 (looks like a ceiling/tie in the fit). W1-based entries of other teams mostly landed below W1 (CQUPT -13, 메타몽 -14, Lucifer lf-010 -49, lf-009 +14).
- Aman pushed v9 (CLI token refreshed via hidden prompt), warmup succeeded (272.5 s), official submitted.
- **v9 BOARD: PCS 1971 [1843, 2100], mean 0.9255, 0.712 km, GT 0.704 m, entry rank 37 [28-45], team rank 20. Host W1 in the same refit: 2259 (0.9437, 0.981 km). v9 vs W1: -0.018 mean, -0.27 km/incident, about -288 PCS.** Verdict: nudge A hurts on the board, as v8's start-now did. **NuRec called the direction 3 of 3 (weak), local nuPlan 0 of 3.** Size predicted by neither.

### 2026-11-12/13 Last-slot search (until Aman decides on Nov 15; default plain W1 as v10)
- Proxy check on host data (agent): only 3 board entries map to host local results, so no local metric can be validated (n = 3, 22 metrics tried). Host research log: a change counts only if it helps on BOTH nuPlan and NuRec; run-to-run noise ~0.5 points nuPlan, ~3 NuRec.
- W1 failure census: NuRec base (440) at-fault incidents 61 = off-road 42, front collision 18, lateral 1; loss shares low progress 45%, off-road 30%, front collision 13%. Fresh nuPlan W1 (691): off-road 36%, stuck 34%, low 20%, front collision 6%.
- Hybrid driven output: impossible on W1 (waypoints model has no unicycle action config).
- **Box-based emergency brake** (offline replay on W1 shadow logs, `aeb_offline.py`, `aeb_timing.py`; ego box 4.9 x 2.0 m, constant-velocity boxes): NuRec fires in 18/19 at-fault collision scenes and 5/194 clean (H 1.0 s), but >= 0.5 s before the collision in only 9-10/19; nuPlan catches 0/3. Not built.
- **Candidate 1, waypoints 3-seed ensemble**: NuRec 4 of 12 chunks (147) **-0.0227 [-0.069, +0.024], W25 / L57**, new zeros 6 / fixed 7; noise floor (W1 rerun, 167) -0.013 W45 / L35. Fails the NuRec half of the gate; dropped.
- Ops: fresh-part HF downloads ~3 MB/s (~2 h per part); `cluster/fetch_parts.sbatch` pre-fetches parts in parallel; NuRec memory requests cut to 15 GB.
- **Candidate 2, slow-down v1 (my design error)**: retimed every plan to 0.9 of its speed, but the model replans from the already-slowed speed, so the cut compounded (NuRec chunk 0 -0.361, W3 / L28, distance driven e.g. 67 to 16 m). Caught; all v1 runs cancelled and discarded. v2 = cap anchored to the model's planned late-plan speed (unit check: settles at 10.8 = 0.9 x 12 m/s).
- **Cap 0.9 (C9) on fresh nuPlan** [L-fresh, n=500]: **-0.0129 [-0.021, -0.005], W2 / L89**, new 1 / fixed 2 (pure progress cost). Dropped.
- **Candidate 3, cap 0.8 in turns > 15 deg (SC)** [L-fresh, 691]: +0.0002 [-0.005, +0.006], W5 / L24, new 1 / fixed 3; neutral on nuPlan; **NuRec untested** (both R6000 nodes drained: ins046 waiting for a reboot behind another user's 14-day CPU job; ins047 "Kill task failed", needs an admin).
- **NuRec cannot run on other GPUs**: L40/L40S/H100 nodes run driver 550.54.14; the NRE renderer is built on OptiX 9.0, whose runtime comes from the host driver and needs R570+ (R6000 nodes have 575.57.08); CUDA forward-compat does not cover OptiX. Not attempted.
- **Candidate 4, controller gains** [L-fresh]: GH heading_weight 2.0 (400) -0.0047 [-0.012, +0.001], 2 new zeros; GS rel_front_steering_angle_weight 2.5 (300) -0.0028 [-0.010, +0.001], 1 new zero. Both break the same clean scene. Dropped.

### 2026-11-13 (morning) SC and ST on NuRec; last-slot search closed
- R6000 nodes back ~07:50 (LEDGER time, 11-13). SC 8-scene check identical to W1 on all 8 (cap rarely binds: the model already slows itself in turns).
- **SC on full NuRec (440)**: +0.0002 [-0.012, +0.012], W86/L95, new zeros 3, fixed 6; at-fault 58 vs 61 (off-road 41 vs 42, front collision 16 vs 18), km/incident 1.137 vs 1.088. Inside rerun noise; with nuPlan +0.0002 (691), no effect.
- **ST (F 0.6 when the plan turns > 10 deg)**: fresh nuPlan (300) -0.0079 [-0.015, +0.001], W4/L43, fixed 1; NuRec (440) -0.0042 [-0.020, +0.011], W76/L106, new zeros 7, fixed 13, at-fault 52 vs 61 (off-road 35 vs 42), corridor exits 12 vs 9, km/incident 1.247 vs 1.088, distance 64.9 vs 66.4 km. A binding turn cap cuts NuRec off-road somewhat but costs progress on both; dropped.
- Last-slot result: 7 candidates (3-seed ensemble, hybrid output, box AEB, slow-down cap, SC, ST, controller gains), none passed the both-tracks gate. Recommendation: plain W1 as v10.

### 2026-11-13 (afternoon) Aman: "we still have 2 days"; three checks
- Board refit (246 entries): eligible best SymPhi 2322, nuVAIL 2319, Lucifer 2306; host W1 2290; CQUPT 2280, 메타몽 2279. Two W1-based entries with higher mean than W1 had lower PCS (메타몽 1112b 0.9475 -> 2256; Lucifer lf-012 0.9462 -> 2262 vs W1 0.9437 -> 2290): small mean gains do not map to PCS.
- Route agreement guard (offline, W1 shadow logs; route served from 40 m ahead): off-road median max plan-to-route distance 3.5 m vs clean 2.0 m; ~5 clean scenes flagged per off-road scene; drift happens in the first 40 m where no route is served. Not viable.
- Low-progress anatomy (fresh 691): 571 score 1, 63 low (27 in 0.9-1.0), 25 stuck, 32 zeros; low scenes start slow and accelerate slowly. Same family as v8/v9's target; not pursued.

### 2026-11-13 (evening) Deep research sweep, Alpamayo 2 Edge, LinkedIn (Aman's request)
- Deep-research workflow: 101 agents, 19 sources, 25 claims verified, 6 killed.
- Alpamayo 2 Edge (HF nvidia/Alpamayo2-Edge, public 11-10; weights OpenMDW-1.1, code Apache-2.0; ~2.65B = 2.45B Nemotron/SigLIP2 backbone + 0.2B flow-matching action expert; 64 waypoints / 6.4 s; 6 camera slots, 22 frames, 20 ego poses at 10 Hz, nav text; 15.15 km per at-fault incident on 875 PAI NuRec scenes, self-reported). Peer threads: strong on nuReasoning only after full fine-tuning (51k rows, ~1 GPU-day/epoch), 2.3-2.8 s per plan at K=6. For nuPlan: off-rig (3 cameras at 2 Hz), Alpamayo 1/1.5 zero-shot had scored 1288/1362, latency and licence unresolved. Not pursued.
- Others assessed: SimWAM (arXiv 2608.07468; NAVSIM v1 91.9 after RL; licence contradictory), ZTRS (2510.24108; +0.6 RC on HUGSIM), verifier / Best-of-N methods (DriveSafer, DriveVer, DriveReward; need training, +0.1-0.9 PDMS). None fits.
- LinkedIn (Aman's login, Chrome): KE:SAI "Latent TransFuser-K1" = py123d v0.2 (already used); their On-Policy Distillation (AlpaSim 86 vs 80 IL, preliminary) and GIGAFLOW reproduction announced, not released. No nuPlan-track write-ups.

### 2026-11-13 (night) to 11-14: on-policy distillation (DAgger) of W1 (Aman: "might as well")
- Idea from KE:SAI's announcement. W1 drives training scenes; label at each visited state = human logged future blended back from the current pose over 2 s (human pace if > 3 m off). Teacher signal via `send_recording_ground_truth=true` (local collection only). Decoder-only fine-tune (14.9M of 67.1M params), backbone frozen.
- Code: `src/g2_dagger/entry.py` (records inputs + human trajectory; optional exploration noise p 0.5, lateral U(+-0.8 m) over 2 s, speed x U(0.8, 1.2)), `src/g2_dagger/train.py` (labels + fine-tune, 340 lines), `cluster/dagger_collect.sbatch`, `cluster/dagger_train.sbatch`.
- Training scenes: 319 local scenes, log-disjoint from the 691 fresh gate scenes. Collection 16 jobs (4 chunks x clean + 3 noise seeds).
- **Sampler-exact "served" loss** (innovation): W1 serves the 8-step Euler integral from the zero state (noise temperature 0), which the released flow-matching loss (random-noise paths) never trains; we unroll the 8 steps differentiably and apply masked L1 to the label. Check: unrolled vs sampled 0.000 m; sampled vs recorded 0.010 m (A6000 vs L40S rounding). Whole policy kept in eval mode (no BatchNorm drift). Smoke: held-out ADE to labels 2.207 -> 1.972 m after 1 epoch.
- Best-of-N self-imitation dropped: noise seed vs clean on 79 scenes 0.780 vs 0.893, W2/L14; noise fixed none of W1's 6 failures.
- Compute wall: all L40S/L40/H100 nodes allocated; Vultr checked with Aman (no L40S/H100 available anywhere); other GPUs cannot run MTGS (sm 8.9/9.0).
- Round 1 (79 scenes, 4 epochs): D1 (human labels everywhere) loses on 4 of 5 parts (held-out ADE best after epoch 1, then rising: overfit). D1o (human labels only >= 1 m off the human path) flat.
- 11-14 ~09:00-13:30 UTC: Insomnia unreachable (VPN down); jobs kept running.
- Round 2 (234 scenes, 4,236 samples, 2 epochs): D2o (anchor 1.0 m), D2h (0.5 m). Val ADE slightly worse than W1's own plans (D2o 0.571 -> 0.598 m).
- **Pooled 691 fresh nuPlan vs W1**: D1 -0.0358 [-0.053, -0.019], W68/L113, new zeros 20 / fixed 11, at-fault 4 -> 9, off-road 25 -> 30; D1o -0.0036 [-0.0076, -0.0003], W49/L38, at-fault 4 -> 5; D2h -0.0053 [-0.011, -0.000], W50/L39, at-fault 4 -> 5; **D2o +0.0025 [-0.0015, +0.0068], W64/L22, new 1 / fixed 1, off-road 25 -> 25, at-fault 4 -> 4**. Per-part D2o: -0.010, -0.001, +0.005, +0.001, +0.009, +0.002, +0.012. Validity: 691/691 scenes, same scenes and GPU class as baselines, W1 bit-identical reruns. Power: 90% half-width ~0.004 at n = 691, so D2o's +0.0025 is unresolvable. Not passed.
- D2o NuRec (12 chunks, 13907530-41) could not start before the deadline (ins046 8/8 R6000 GPUs taken by other users; ins047 memory fully allocated by CPU jobs; Slurm estimate 11-20). Last-slot search closed: v10 = plain W1.
- Board 11-14 14:23 UTC (251 entries): CQUPT 2359, SymPhi 2359, nuVAIL 2353, Lucifer 2336, host W1 2317, 메타몽 2303; ours v9 1994.

### 2026-11-14 (evening) to 11-15: route leash from a leader's entry name (Aman: "can we do anything from the leader's entry name")
- CQUPT's 2359 entry `geo1134-turngate30-pathonly-leash-20261113-v2` (also as `BoundaryDrive`): mean 0.9677, 1.463 km, GT 0.512; their earlier W1-like entry 2307. No public write-up.
- Our reading (guess): keep the plan's path near the route, speed kept ("pathonly"), outside sharp turns ("turngate30"). Built `src/g2_leash/entry.py` (128 lines): cubic Hermite reference from ego heading onto the served route (starts ~42 m ahead), then the route; Frenet projection; lateral offset clamped to +-M, arc length kept; skipped if the reference turns >= 30 deg within reach, below 1 m/s, or with no route; any exception falls back to the model plan. Unit checks passed (`analysis/pool_scripts/leash_unit.py`).
- 21 runs (7 fresh parts x M 0.3/0.5/1.0, jobs 13908735-41), leash active in all, 0 failures. Paired vs W1 on 691: L03 -0.0072 [-0.0132, -0.0014], W25/L32, new zeros 6 / fixed 1, off-road 25 -> 29, at-fault 4 -> 5; L05 -0.0016 [-0.0059, +0.0027], W22/L29; L10 -0.0000 [-0.0001, +0.0001], W19/L24. **Negative**; NuRec not runnable. Rejects our reading on W1/nuPlan, not CQUPT's method.

### 2026-11-15 v10 = plain W1 submitted (track's last slot)
- `limits`: 1 official, 1 nuplan-warmup left; terms accepted (official-2026-08); `ecr-login` OK; `v10` absent from the registry. Aman entered the CLI token via the hidden prompt; I ran push / warmup / official on his instruction ("run all the steps").
- Push digest sha256:db5833d6…; warmup 77c74265 SUCCEEDED 32/32, 269.6 s; official 2f9b4489 SUCCEEDED 1,000/1,000, 1,194.5 s, dist to GT 0.58975 = host W1's.
- Board 10:36 UTC: PCS 2320 [2155, 2485], rank field 13, mean 0.93955, 0.841 km; host W1 2332 (0.94369, 0.981 km). Same GT distance, different mean: board not bit-identical across runs of one driver (메타몽 1103a, W1-like, also 0.93955 / 0.841). Team order: CQUPT 2370, SymPhi 2370, nuVAIL 2360, Lucifer 2350, [host 2332], us 2320, 메타몽 2319. 5th eligible at that time.
- ~11:00 UTC: D2o NuRec jobs cancelled on Aman's instruction; report written with what we had. Aman's closing view of the leaderboard (paraphrased): with entries this close and the same driver scoring differently, the board is a weak judge of capability.
- Report finalised (author block filled, v10 result, leash, D2o "could not run on NuRec before the deadline").

### 2026-11-16 Cluster cleanup; report accepted
- Storage assessment, archive to the Mac, cluster-only code committed, 1.4 TB folder deleted (job 13924597, 18 min); fileset 8.1 -> 6.7 TB used.
- 22:57 UTC: report uploaded after Aman's review and his token refresh; ACCEPTED (a135197d…, sha256 511e2d83…, 45,330 bytes).

### 2026-11-18 Organiser final runs; final board
- Organiser "noise reduction: 3-run mean" records (11-18 14:26 UTC) for SymPhi, CQUPT, nuVAIL, Lucifer (lf-009), 메타몽 (metamong-1103a, same numbers as our v10). None for amanupg. Final board read 11-21: v10 2450, 18th of 63 teams by best-entry PCS.

---

## 4. All numbers tables

### 4a. Official (BOARD)
See section 2 for our four entries, warmups and standings. Reference entries (BOARD):

| Entry | Date of read | PCS | Mean scene | km/at-fault | GT m |
|---|---|---|---|---|---|
| Public py123d v0.1 model_0014 (host 014, YAX_NAM, Lucifer) | 10-03 | 1484 / 1487 / 1485 | 0.848 | | |
| Same (host 014 / YAX_NAM / Wj) | 11-12c | 1507 / 1503 / 1505 | 0.853 / 0.852 / 0.852 | | |
| go_straight_with_delay_v2 (host) | 10-02 | 1299 | 0.799 | | |
| SimScale DiffusionDrive / LTF / GTRS (host and others) | 10-02 | 1073 / 1019 / 722-1014 | 0.772 / 0.738 / 0.526-0.761 | | ~2.2 |
| WA-JEPA (Lucifer AI adapter, Sep 10) | 10-02 | 1022 | 0.762 | | |
| Released joint64 seed 0 unchanged (4 teams) | 11-08 / 11-12c | 2074-2083 / 2191-2199 | 0.9205 | 0.834 | 0.669-0.671 |
| Host W1 = released waypoints seed 1 (093) | 11-08 / 11-12 / 11-12c | 2181 [2063, 2298] / 2247 / 2259 [2130, 2389] | 0.9437 | 0.981 | 0.590 |
| Host joint32 seed 2 (120) | 11-09 | 1949 | 0.9217 | 0.678 | 0.627 |
| Best non-host, 10-21: SymPhi / nuVAIL / Lucifer | 10-21 | 1948 / 1858 / 1711 | 0.944 / 0.947 / 0.890 | 0.875 / 0.675 / 0.528 | 0.747 / 0.556 / 0.737 |
| Best, 11-12c: SymPhi sp-1029a / nuVAIL nu-vail-36 / Lucifer lf-009 | 11-12c | 2288 / 2287 / 2273 | 0.9693 / 0.9883 / 0.9454 | 1.766 / 3.788 / 1.039 | 0.678 / 0.949 / 0.585 |
| Host W1 093 (same checkpoint as our v10) | 11-13 / 11-14 / 11-15 08:50 / 11-15 10:36 / final 11-21 | 2290 / 2317 / 2325 / 2332 / 2478 | 0.9437 | 0.981 | 0.590 |
| amanupg v10 | 11-15 10:36 / final | 2320 [2155, 2485] / 2450 [2303, 2597] | 0.93955 | 0.841 | 0.58975 |
| 메타몽 metamong-1103a (W1-like, same numbers as v10) | 11-15 / final submission / final 3-run mean | 2319 / 2455 / 2454 | 0.9395 | 0.841 | 0.590 |
| CQUPT leash entry | 11-14 / final (3-run mean) | 2359 / 2547 (2546) | 0.9677 | 1.463 | 0.512 |
| Final top 4 (best entry) | final 11-21 | SymPhi 2573 / CQUPT 2547 / nuVAIL 2546 / Lucifer lf-013 2528 | 0.9693 / 0.9677 / 0.9862 / 0.9494 | 1.766 / 1.463 / 2.40 / 1.364 | |
| Plain joint64 seed 0 teams (BlindDrive, TerraDrive, Team gh, Apex) | final | 2448 / 2444 / 2444 / 2431 | 0.9205 | 0.834 | |

### 4b. Local closed loop: phase-by-phase key results
| Date | Comparison | Set, n | Result |
|---|---|---|---|
| 09-29 | WA-JEPA vs Alpamayo v0.3 | L-early 001, 100 | 0.958 vs 0.759, +0.198 [+0.131, +0.265], W35 / L2 |
| 09-29 | same | L-early 010, 100 | 0.729 vs 0.510, +0.219 [+0.123, +0.312], W41 / L11 |
| 09-29 | WA-JEPA cameras grey / constant velocity | L-early 001 | 0.392 / 0.578 |
| 09-30 | WA-JEPA vs LTF / DD / GTRS | L-early 010 | +0.029 / +0.039 / -0.001 (all CI span 0) |
| 09-30 | WA-JEPA zero-shot on PAI (crop / resize) vs Alpamayo | PAI-local, 40 | 0.250 / 0.301 vs 0.668 |
| 10-01 | WA-JEPA + GTRS judge R1 m1 vs WA-JEPA | 300 (001/010/005) | 0.917 vs 0.877, +0.040 [+0.019, +0.062], W18 / L8 |
| 10-01 | same | shard 005 (untouched), 100 | +0.041 [+0.001, +0.081], W6 / L2 |
| 10-02/03 | + route snap vs judge | 300 | +0.006 [-0.014, +0.026] |
| 10-02/03 | + time scale 1.25 | 300 | 0.60-0.67 (-0.21 to -0.33) |
| 10-03 | public py123d 0014 | L-tune per shard | 0.787 / 0.656 / 0.841 |
| 10-03 | py123d + 1.10 straight-only warp | L-tune | +0.010 [-0.000, +0.020], W64 / L8 |
| 10-04 | judge m3 R1 + warp skip-judged | L-tune 300 / part 013, 100 | +0.032 [+0.015, +0.049] / +0.049 [+0.011, +0.092] |
| 10-07 | judge m3 R2 + warp | L-tune / L-held 261 | +0.043 [+0.020, +0.066] / +0.058 [+0.034, +0.082] |
| 10-09 | judge m3 R3 + warp (public base) | L-tune / L-held / L-fresh 193 | +0.061 [+0.035, +0.088] / +0.063 [+0.032, +0.093] / +0.113 [+0.080, +0.149] |
| 10-09 | fine-tune A plain vs public | L-tune / L-held / L-fresh | +0.059 / +0.047 / +0.036 (all CI > 0) |
| 10-10 | FT A + R3 vs public | L-tune / L-held / L-fresh | +0.073 / +0.079 / +0.114 |
| 10-10 | FT A + R3 vs public + R3 | all 754 | +0.011 [-0.002, +0.025], W116 / L95 |
| 10-11 | A2 plain vs A plain / A2+R3 vs A+R3 | 561 | +0.011 [+0.001, +0.023] / -0.009 [-0.020, +0.002] |
| 10-11 | soup + R3 vs A + R3 | L-tune | +0.001 [-0.011, +0.014] |
| 10-12 | stall rescue 1 m vs Q | all 754 | +0.030 [+0.020, +0.039], W35 / L4 |
| 10-12 | stall 3 m vs 1 m | all 754 | +0.013 [+0.008, +0.019], W31 / L2 |
| 10-18 | stall 5 m vs 3 m | held-out + fresh 454 | +0.008 [+0.002, +0.016], 3 new zeros (not adopted) |
| 10-18 | q:3 (v6) vs public | all 754 | 0.852 vs 0.724, +0.128 [+0.108, +0.149], W212 / L52 |
| 10-20 | A31 epoch 31 vs q:3 | L-tune | -0.003 [-0.016, +0.011] |
| 10-23 | v0.2 joint64 seed 0 (N1) vs public 0014 | L-tune | 0.908 vs 0.761, +0.147 [+0.114, +0.182], W96 / L17 |
| 10-23/25 | v0.2 levers (ensembles, ftN, WiSE, MPC gains, inference options, seeds, target points, sampling, extrapolate_route) | L-tune / L-held | none positive on held-out (see section 3) |
| 10-26 | start-now K=3 vs seed 0 | all 754 | +0.015 [+0.009, +0.021], 0 new zeros |
| 11-05/07 | CL decoder r1 / r2lat / r2lat_hi / r2self_hi vs v8 | L-tune 300 | -0.013 / -0.016 / -0.026 / -0.003 |
| 11-07 | idx 19 + K=3 vs v8 | L-held 261 | -0.0124 [-0.0266, -0.0002], 4 new zeros |
| 11-07 | warp 1.10 + K=3 vs v8 | 561 | -0.0053 [-0.0129, +0.0013] |
| 11-10 | our W1 vs host-published W1 | 200 (001+013) | 182/200 identical, -0.0000 [-0.0001, +0.0000] |
| 11-10 | waypoints 3-seed ensemble vs W1 | 557 | +0.0074 [-0.0047, +0.0202], W34 / L48 |
| 11-11 | nudge A / B vs W1 | L-tune (40 firing scenes, pooled over 552) | +0.0129 / +0.0164 |
| 11-11 | nudge A / B vs W1 | L-fresh 600 | +0.0118 [+0.0051, +0.0198] W14 / L0 / +0.0134 [+0.0063, +0.0220] W16 / L0 |
| 11-12 | nudge A vs W1 | L-fresh part 015, 91 | +0.0231 [+0.000, +0.054], W3 / L0 |
| 11-12 | cap 0.9 vs W1 | L-fresh 500 | -0.0129 [-0.021, -0.005], W2 / L89 |
| 11-12 | turns-only cap 0.8 vs W1 | L-fresh 691 | +0.0002 [-0.005, +0.006], W5 / L24 |
| 11-13 | gains GH / GS vs W1 | L-fresh 400 / 300 | -0.0047 / -0.0028, new zeros 2 / 1 |
| 11-13 | ST cap 0.6 in turns > 10 deg vs W1 | L-fresh 300 | -0.0079 [-0.015, +0.001], W4 / L43 |
| 11-14 | DAgger D1 / D1o / D2h / D2o vs W1 | L-fresh 691 | -0.0358 [-0.053, -0.019] / -0.0036 [-0.0076, -0.0003] / -0.0053 [-0.011, -0.000] / +0.0025 [-0.0015, +0.0068] W64 / L22, at-fault 4 -> 9 / 5 / 5 / 4 |
| 11-15 | route leash L03 / L05 / L10 vs W1 | L-fresh 691 | -0.0072 [-0.0132, -0.0014] W25 / L32 / -0.0016 [-0.0059, +0.0027] W22 / L29 / -0.0000 W19 / L24 |

### 4c. NuRec (local)
| Comparison | n | Result |
|---|---|---|
| Base pass W1 vs joint64 s0 | 440 | 0.685 vs 0.668; km/at-fault 1.088 vs 1.096 |
| W1 rerun vs W1 (noise) | 14 / 167 | -0.0016 [-0.0056, +0.0012] (8/14 differ) / -0.013, W45 / L35, 5 new / 3 fixed zeros |
| Nudge B, chunk 0 | 14 | -0.0924 [-0.311, +0.092], 2 new zeros |
| Nudge Bs, chunk 0 / group 0 | 14 / 32 | +0.0443 / +0.0341 [-0.061, +0.127] with 1 new at-fault collision |
| Nudge A, acted / never acted | 79 / 88 | +0.0461 [-0.0117, +0.1041], at-fault +3 / -1 / -0.0112 (noise) |
| Nudge A, all firing scenes | 167 | +0.0159 mean, new zeros 4 / fixed 3, at-fault +4 / -1; +0.0060 per scene over 440 |
| v8 start-now vs j64s0 | 188 | -0.0009 [-0.024, +0.019], W62 / L21, 4 new zeros (3 at-fault), 0 fixed |
| Waypoints 3-seed ensemble vs W1 | 147 | -0.0227 [-0.069, +0.024], W25 / L57 |
| Slow-down v1 (bugged, discarded) | 36 | -0.361, W3 / L28 |
| SC cap 0.8 in turns > 15 deg vs W1 | 440 | +0.0002 [-0.012, +0.012], W86 / L95, new 3 / fixed 6, at-fault 58 vs 61 |
| ST cap 0.6 in turns > 10 deg vs W1 | 440 | -0.0042 [-0.020, +0.011], W76 / L106, new 7 / fixed 13, at-fault 52 vs 61, corridor 12 vs 9 |
| DAgger D2o vs W1 | 0 | never ran (R6000 blocked; jobs cancelled 11-15) |

### 4d. Open-loop and offline
| Item | Result |
|---|---|
| WA-JEPA pilot round 1 (1,091 val, 160 turns) | released ADE 0.654 / FDE 1.831; route FT 0.676 / 1.890; control 0.682 / 1.910 |
| WA-JEPA pilot round 2 | released 0.681 / 1.892; TP-only 0.699 / 1.976; route lr 1e-5 0.697 / 1.919; control 0.691 / 1.909 |
| CL decoder r1 held-out L1 to labels | 2.914 to 2.652 m (off-log 4.434 to 3.805, n=75) |
| CL decoder r2lat_hi cross-track | 0.594 to 0.571 m; off-log 1.402 to 1.222 m (n=72) |
| Released seed 0 5 s distance bias vs log (sim, n=96) | mean -1.49 m, median -0.66 m |
| Target point reimplementation | 0.0 m difference on 205 random routes |
| WA-JEPA cached-feature inference vs reference | max diff 0.0000 m |
| Stall-nudge trigger (shadow logs, 552) | 14/23 stuck, 4/38 low, 1/469 clean, 0 failing |
| AEB offline (W1, H 1.0 s) | NuRec 18/19 collision scenes, 5/194 clean; nuPlan 0/3 |

### 4e. PCS proxy (PROXY)
| Fit | Result |
|---|---|
| 11-04, 20 of our policies x 552 | K=3 3.93, K=1 3.99, idx19 4.00, seed 0 3.75, WA-JEPA + judge 2.62, v6-era 1.0-2.0, public 0014 0.66; std ~0.2 |
| 11-07 refit, 22 subjects | k3idx19 - v8 +0.23 / +0.02 / +0.36; tw110 - v8 +0.24 / +0.02 / +0.11 |
| 11-09 host population (12 checkpoints x 1,475) | seed 2 3.93-3.97 vs seed 0 3.34-3.40 |
| 11-09 validity check (host + ours, 550) | v8 above seed 0 by +0.27 to +0.30; the board says -225. Proxy failed for situational rules. |

---

## 5. Final system in full

### FINAL entry (v10, submitted 2026-11-15): plain W1, `local/w1:1` pushed as `teams/amanupg:v10`
- Model: py123d_garage v0.2.0 `ltf-base-waypoints-68M` posttrain seed 1 (`model_1.pth`, HF `kesai-labs/py123d_garage_pretrained_checkpoints` revision 56edbe90, Apache-2.0 at that revision; repo relicensed CC BY-NC-SA 4.0 on 10-29, noted in NOTICE). Description of the model as in the v9 block below, without any add-on.
- Driver: py123d_garage v0.2.2 `GarageDriver`, standard entrypoint, default MPC gains (no controller changes).
- Image digest sha256:db5833d60444c06e74381d111f71f96c84260676de344fba86d53590927ad388 (image id db5833d60444; docker showed 36.1 GB, likely a display artefact, not re-measured). Checked earlier in closed loop (LEDGER line 927).
- Official: 1,000/1,000 valid, 1,194.5 s of 3,000 s; dist to GT 0.58975 = host W1. BOARD: 2320 (11-15) / 2450 (final).
- Why plain: nothing we built beat it under the both-simulator gate (sections 3, 7); the board had punished both previous add-ons.
- Kept on the Mac: W1 weights folder (`cluster_archive/weights_py123d_v0.2.0/ltf-base-waypoints-68M`, 817 MB) and D2o decoder (`cluster_archive/dagger_models/D2o`, 273 MB).

### v9 = `local/w1n:1` (was the best entry until v10; final refit 2091)
- Base model: py123d_garage v0.2.0 `ltf-base-waypoints-68M`, posttrain stage, **seed 1** (`model_1.pth`, sha256 ae1619d5…, = HF LFS oid; config.yaml sha256 6a2f472d…; HF `kesai-labs/py123d_garage_pretrained_checkpoints` revision 56edbe90, 2026-10-21, Apache-2.0 at that revision). Latent TransFuser, camera-only, **67.1 M parameters, 825 tensors**, strict load. Flow-matching planner, "waypoints" driven output, 64 waypoints over 6.4 s plus a 64 m path, 2 Hz replanning. Inputs: front camera at the current time and 1 s earlier, ego status (speed etc.), up to 3 route target points at 40 / 60 / 80 m; nuPlan sensor rig `sensor_rig_nuplan.yaml`. Trained by the host on PAI AV + NuRec + nuPlan train/val.
- Driver: py123d_garage v0.2.2 `GarageDriver` (alpasim_grpc 0.54.0 built from NVlabs/alpasim e2e_challenge @ e121e59), MPC controller with default gains.
- Our add-on: `src/g2_nudge/entry.py` (208 lines) installed by monkey-patching `TransfuserPolicy.forward` and `GarageDriver._plan` (no py123d code changes). Mode A, K = 3, latch on, creep off: when the ego is slow (< 0.5 m/s), the plan moves < 1 m in 2 s, and the model's own detected boxes show nothing in a 25 m corridor along ego plus route (|lat| < 2 m), no crossing moving vehicle/two-wheeler within 30 m and no static object within 15 m ahead / 8 m lateral, for 3 consecutive plans, it drops the waiting prefix of a wait-then-go plan so motion starts now (tail extended at constant velocity); after the first action it is latched and acts on any single firing plan.
- Image: `container/Dockerfile.w1n` FROM `local/w1:1` (itself FROM `local/n:1` = py123d v0.2.2's own submission Dockerfile, uv from PyPI, CUDA base image), `ENV PYTHONPATH=/opt/addons G2_NUDGE_MODE=A G2_NUDGE_K=3`, ENTRYPOINT `python -m g2_nudge.entry`; `/opt/NOTICE` (NOTICE.w1n) lists every third-party component, source, revision and licence; Apache-2.0 LICENSE. 12.8 GB. Digest sha256:da1fe936e1267f9e6ca8c5fb0a98471b5ba4d7437da7f111b497a622fb66f61d.
- Runtime: 1,235 s of 3,000 s official budget for 1,000 rollouts; W1 Drive call 0.050 s on L40S [local].

### (11-13 text, now superseded: v10 was submitted 2026-11-15, see FINAL entry above) Planned last entry (v10, not submitted): plain W1, `local/w1:1`, image id db5833d60444 (docker shows 36.1 GB, likely the same display artefact seen for q:2/q:3; actual size not re-measured), standard garage entrypoint.

### Other submitted or built systems (all recorded)
- **v6 = `local/q:3`**: py123d_garage v0.1.1 @ 288d34c; our **fine-tune A** of `resnet34_v0.1.0/model_0014.pth` (ResNet-34 image encoder, latent BEV query in place of lidar, 3 front cameras stitched 1024x256, ego velocity/acceleration, driving command, target point 45 m along the route, 8 poses at 0.5 s); model.pth sha256 8691cc01…, config a0b17835…, public nuPlan rig 453ddf94…. GTRS-Dense critic `gtrs_dense_resnet_sim_reward_navhard.ckpt` (sha 8dad0395…) + vocabulary `navsim_16384.npy` (sha e8c29cfc…) from `OpenDriveLab/SimScale` (Apache-2.0): plan substitution within radius 3 m if s(g) - s(P) > 3 (s = log NC + log DAC + 3 log EP); stall rescue (plan ends < 3 m: best path moving >= 3 m with NC, DAC > 0.9, margin 1); 1.10 time warp on kept plans with heading change < 10 deg over 4 s. Env: `GARAGE_JUDGE=gtrs GARAGE_JUDGE_MARGIN=3 GARAGE_JUDGE_RADIUS=3 GARAGE_TIME_SCALE=1.10 GARAGE_TS_MAX_TURN_DEG=10 GARAGE_TS_SKIP_JUDGED=1 GARAGE_JUDGE_STALL_M=3 GARAGE_JUDGE_STALL_MARGIN=1`. 12.79 GB. Driver peak 8.3 GiB with 2 concurrent sessions (report draft).
- **v8 = `local/n2:1`**: released v0.2.0 `ltf-base-joint64-68M` posttrain seed 0 (`model_0.pth`, sha256 d7113ef3…) + `src/g2_addons/entry.py` start-now K=3 (md5 1252015d…). 12.6 GB.
- **WA-JEPA + judge (`v4` reserved, warmup only)**: `alpasim-jepa/wajepa:v2-judge-6672747`, Docker id dde3c672…, 5.64 GB; WA-JEPA (V-JEPA 2.1 ViT-L 384 encoder + 12-layer flow predictor, 788 M params, 4 cameras x 4 frames at 256x512, fp32 weights under bf16 autocast, 4 Euler steps, `flow_inference_seed: 1`) + GTRS judge R1 m1. Drive 0.39 s, GPU 5,716 MiB [local, L40S].
- Built, never submitted: `wajepa:dev` (2a5b22e5…), `wajepa:v1-4662979` (53019680…), `local/q:1` (ae4b8656b624), `local/q:2` (3f315f660f72), `local/n:1` (0a06ba20a19c, plain joint64 seed 0), `local/n3:1` (31b8fd62e222, joint64 seed 2), `local/w1:1` (db5833d60444). A `container/Dockerfile.p` recipe (public py123d + straight-only warp, "candidate P") exists; whether it was ever built is not recorded.

### Training recipes of everything we trained
| Run | Init | Data | Schedule / optimiser | Precision / compile | Hardware, time | Outcome |
|---|---|---|---|---|---|---|
| WA-JEPA route pilot round 1 (13303410) | released WA-JEPA, encoder + projector frozen, context features cached (12.6 MB/sample) | ~9.8k train samples (154 shards, 18 batches of nuPlan 123D logs, 4 cameras incl. b0), 1,091 val from 20 val logs; anchors every 4 s | 3 epochs, 1,726 steps, lr 1e-4; trainable 58.6 M of 788 M (trajectory stream + zero-init target-point encoder) | trainable params fp32 under autocast | 1 A6000, ~11 samples/s; data stage 6 h | worse than released [OL] |
| WA-JEPA route pilot round 2 (13310920) | same | ~4.9k train (77 shards; throttled downloads), same val | 3 runs, 878 steps each: TP encoder only lr 1e-4; route + trajectory lr 1e-5; control lr 1e-5 | same | 1 A6000 | all worse; paused |
| py123d fine-tune A (13287171) | public v0.1 model_0014 | 430 logs (362 train + 68 val), 108,414 samples/epoch, 3 front cameras, no lidar; 133 GB cache on node-local disk (5.3 h) | py123d nuPlan-only preset `ltf_nuplan_trainval`, 15 epochs, cosine warm restarts T_0 1, T_mult 2, batch 64, 25,395 steps; optimiser = py123d default (not recorded in ledger) | bf16-mixed with fp32 master weights; torch.compile max-autotune | 1 RTX PRO 6000 Blackwell (ins046), ~485 samples/s, 1 h 8 min training | used in v6 |
| Fine-tune A2 (13320641) | A epoch 15 | disjoint 300 logs (271 train + 29 val), 72.8k samples/epoch, data 5.3 h | 15 epochs, 17,055 steps | same | 1 A6000 (ins094) | no gain with recipe |
| Soup | A + A2 | | 666 float tensors averaged | | CPU | rejected |
| Fine-tune A31 (13569405) | public model_0014 | same 430 logs, 108,414 samples | 31 epochs, 52,483 steps | same | 1 A6000 (ins094), 8.9 h (data 4.3 h, training 4.5 h) | no gain |
| v0.2 fine-tune ftN (13648035) | released joint64 posttrain model_0 | 400 logs (362 train + 38 val), 497,784 samples, front camera only | py123d `latent_transfuser:nuplan_posttrain` (backbone frozen, target-point dropout), 7 epochs, 54,439 steps | compile_mode default (reduce-overhead crashed) | 1 A6000 (ins093), 3.5 h, ~402 samples/s | no gain; WiSE 0.5 / 0.3 no gain |
| CL decoder round 1 (13798308) | released joint64 seed 0 | 687 closed-loop collected scenes (parts 002/004/006/008/009/012/015), 3,982 records, train 3,538 / val 444 | planning_decoder only, py123d flow loss, 4 epochs, 444 steps, lr 2e-5 one-cycle (batch size not recorded; ~32 implied) | | 1 A6000, 21 min incl. env build | worse closed loop |
| CL decoder round 2 r2lat / r2lat_hi / r2self_hi (13823447 / 48 / 13824491) | same | 3,761 records, train 3,354 / val 407 | lr 2e-5 / 1e-4 / 1e-4 (self labels, path loss 0) | | any GPU, 15 min each | worse / worse / flat |

---

## 6. Technologies and tools

- **Simulator and renderers**: NVIDIA AlpaSim (NVlabs/alpasim, e2e_challenge branch, 2023534 then e121e59): wizard, runtime, controller (MPC), trafficsim, evaluator, gRPC egodriver API (`alpasim_grpc` 0.54). MTGS renderer (`alpasim-mtgs-server`) for nuPlan, built for sm 8.9/9.0 (L40S, L40, H100 only). NRE renderer for NuRec scenes (CUDA 12.8, OptiX 9.0, needs host driver R570+; ran only on RTX PRO 6000 nodes). trajdata / UnifiedDataset scene cache.
- **Models**: WA-JEPA (V-JEPA 2.1 ViT-L + flow predictor), Drive-JEPA (borrowed, no run recorded), py123d_garage v0.1.1 (ResNet-34 LTF) and v0.2.0/v0.2.2 (68M flow-matching LTF variants), SimScale samples (LTF, DiffusionDrive, GTRS-Dense), Alpamayo 1.5 (baseline), FlashDrive (PAI bet, handed off).
- **ML stack**: PyTorch 2.8 (cu128), PyTorch Lightning 2.6.6 (py123d training), torch.compile (max-autotune, reduce-overhead, default), bf16 mixed precision, timm 0.9.16, OpenCV 4.12, omegaconf, einops, uv for envs, Hugging Face Hub with hf_xet (token from a 600-mode file), W&B disabled.
- **Containers**: Docker / Docker Desktop BuildKit on the Mac (linux/amd64 builds, amd64 emulation checks), AWS ECR (`teams/amanupg:<tag>`, pushed by Aman), Apptainer 1.4.5 on the cluster (sandbox from `docker save` archives, built on node-local disk), read-only/no-network smoke tests as non-root uid 10001.
- **Cluster**: Columbia Insomnia, Slurm (sbatch, srun, afterok/afterany chains, `--test-only` start estimates, `-p short,burst`, exclude lists for faulty nodes), GPFS department fileset (5 TB quota, later 10 TB), node-local `/local` (200 GB on most GPU nodes, 14 TB on R6000 nodes).
- **GPU types used**: NVIDIA L40S (most nuPlan sims), L40, H100 (sims, official-hardware matching), RTX A6000 (training, decoder runs; not usable for the MTGS renderer), RTX PRO 6000 Blackwell (R6000, ins046/047: fine-tune A, WA-JEPA zero-shot on PAI, all NuRec). Host drivers 550.54.14 (L40/L40S/H100) and 575.57.08 (R6000).
- **GPU-hours (final): 541.2 GPU-h** on Insomnia for alpasim-jepa (sacct, all runs including requeues, as of 2026-11-16 15:41 EST; final because the folder was deleted that day). Earlier per-item figures kept below for detail.
- **GPU-hours**: not recorded in aggregate. Recorded single items: fine-tune A ~6.5 h job (5.3 h data + 1 h 8 min training) on 1 GPU; A31 8.9 h; ftN 3.5 h; A2 data 5.3 h + training (time not recorded); WA-JEPA pilot runs ~6 h data stage each plus training; one failed pilot ran ~12 h; CL decoder runs 15-21 min; local nuPlan 100-scene runs typically 20-35 min on 1 GPU (WA-JEPA 22 min 39 s); NuRec ~3 to 4 min per scene, base pass 24 chunks of ~1 h 50 min (my estimate ~45 GPU-h for the base pass); the full 4-driver NuRec plan would have been ~118 GPU-h (not run).
- **Cloud rentals / cost**: none for this thread. A ~$250-450 Blackwell rental to speed up the NuRec check was proposed on 11-11 and declined by Aman (budget). Total spend: $0 beyond university resources (as far as recorded).
- **Cloud rentals / cost (final)**: none for this thread, $0. 11-11 Blackwell rental (~$250-450) declined by Aman; 11-13 Vultr checked with Aman logged in (all L40S 1/2/4x and 8x H100 plans unavailable everywhere), nothing deployed. Mac used for Docker builds, image checks, report build (tectonic) and analysis.
- **Added 11-13 to 11-16**: on-policy distillation stack (`g2_dagger`: collection driver, sampler-exact trainer), route leash add-on (`g2_leash`), challenge CLI report upload, tectonic for LaTeX, Slurm-run deletion with archive + sha256 verification.
- **Data pipelines**: nuPlan 123D logs from HF `kesai-labs/nuplan` (public), streamed in batches to node-local disk, cached, camera files deleted; WA-JEPA frozen-feature cache; MTGS asset parts fetched per job (`LOCAL_PART`) or pre-fetched in parallel (`fetch_parts.sbatch`); local trajdata cache from public tarballs (`LOCAL_CACHE`); closed-loop data collection (`collect.py`) with DART-style perturbations.
- **Eval harnesses**: `cluster/sim_nuplan.sbatch` (233 lines; DRIVER = a15 / wajepa / samples / garage / garage2 / imagep; per-job gRPC port blocks; slimming; LOCAL_PART / LOCAL_CACHE), `cluster/sim_nuplan_multi.sbatch` (several variants paired in one job on one GPU), `cluster/sim_nurec.sbatch` (per-job NRE unpack on `/local`), `cluster/sim_pai.sbatch`; analysis `src/analysis/report.py` (every config vs its baseline, tuning/held-out separately, infra-failure warnings), `paired_compare.py`, `pool_compare.py`, `firing_sets.py`, `shadow_triggers.py`, `route_audit.py`, `slim_asl.py`, `wise_average.py`; organisers' `summarize_run.py` / `compare_runs.py` and `local_evaluation/evaluate.py` (Drive-IRT) for the PCS proxy.
- **Tests**: `tests/test_driver_history.py` (simulated gRPC, fake policy; history order, camera slots by pixel values, relative poses, padding), `tests/test_driver_pai.py`; `src/analysis/test_target_point.py`; `src/wajepa_route/verify.py`; unit checks for route bridge, snapping, time warp, nudge, creep and slow-down (some in session scratchpad: `test_nudge.py`, `test_creep.py`, `test_bs.py`).
- **Repos**: private GitHub `amanupg/alpasim-jepa-2026` (created 2026-10-05; local history from 2026-09-29). Sibling repos: `amanupg/alpasim-challenge-2026` (PAI), `amanupg/nureasoning-challenge-2026`, `nureasoning-jepa-2026`.
- **Reporting**: LaTeX with the organisers' AlpaSim/NeurIPS-2026-derived style and TikZ (report draft).

---

## 7. Innovations and non-obvious things built (with measured effect)

1. **Paired, deterministic, multi-pool evaluation protocol** for nuPlan: established that the MTGS closed loop is bit-for-bit deterministic on one GPU type (py123d rerun identical on all 300 scenes), so noise = scene sampling; tuning (300) / held-out (261) / fresh (193, later 691) pools, adopt only if positive on all. Effect: caught several tuning-only gains (stall 5 m, idx_start_penalty 15/19, seed 0+2 ensemble, 3-seed ensemble) before submission. Limitation: it shares navtest's benchmark-level bias and did not predict the board for v6, v8, v9.
2. **Calibration of local vs official across model families** (10-02/03): six drivers with official entries showed local navtest inverts the official ranking of model families; led to the pivot from WA-JEPA to py123d.
3. **Radius-limited, margin-gated critic** (GTRS-Dense restricted to paths within R m of the planner's plan, swap only if the score gain > margin): +0.040 [+0.019, +0.062] on WA-JEPA and +0.061 to +0.113 on public py123d across all local pools. Did not transfer to the board (v6), consistent with the NAVSIM-family bias.
4. **Stall rescue** from a failure decomposition (low-progress loss 0.100 > zero-score loss 0.089): +0.030 then +0.013 [local, 754]. Not separable on the board.
5. **Receding-horizon "wait-then-go" diagnosis**: found from plan logs that the policy plans "wait 1.7-4.0 s then go" at every replan so the MPC never starts the car; start-now rule +0.015 [+0.009, +0.021] locally with zero new failures. Shared with the PAI thread (credited in `LESSONS_FOR_AGENTS.md`: "found first on nuPlan by the sibling thread"). On the board it cost ~225 PCS (v8).
6. **Shadow-mode driver logging** (`g2_shadow`): logs the model's own perception (boxes, drivable probabilities, BEV) and plans without changing driving (scores verified identical), so trigger rules are designed and audited offline. Effect: box-gated stall trigger fires in 14/23 stuck vs 1/469 clean scenes, vs 11/23 and 27/469 for v8's start-now; also ruled out an off-road guard (2-3/17 caught) without a single closed-loop run.
7. **Firing-set paired design**: since a rule-based add-on cannot change a scene until it first acts, candidates run only on scenes where the trigger fires in the base pass, paired with a same-job base rerun. Effect: the nudge tuning check used 40 of 552 scenes; NuRec checks used 167-188 firing scenes instead of 4 drivers x 441 scenes (~118 GPU-h). `firing_sets.py` reproduced the live run's 19 firing scenes exactly.
8. **NuRec as a second simulator for add-on direction**: with paired reruns to measure its non-determinism. Calibration: NuRec matched the board's direction 3 of 3 (W1 vs j64s0, v8, v9) while local nuPlan was 0 of 3 (weak evidence, n = 3).
9. **PCS proxy refits** of the organisers' Drive-IRT zoib on our per-scene scores (and the host's), with fit-seed variance; and an explicit validity check that showed the proxy could not see v8's board failure (honest negative).
10. **Board-side controls**: using other teams' unchanged-baseline entries (four identical joint64 seed 0 entries; the host's W1) as free controls for our add-ons; and mapping host board entries to released checkpoints via their READMEs (W1 discovery, after Aman's pointer).
11. **Host-result reproduction**: our v0.2.2 driver reproduces the host's published W1 per-scene results (182/200 identical, mean diff -0.0000).
12. **Image-check protocol**: every submitted image re-run in closed loop from the exact archive on the cluster against the tested configuration: q:1 / q:2 / q:3 200/200 identical (same GPU type), n2 280/300 identical (GPU mix), w1n 200/200 identical; sha256 of checkpoints, configs and add-on code checked inside each image; registry tags listed before every push.
13. **Failure census tooling**: zero-score vs partial-progress decomposition, log-replay control (ego forced on the log) separating unavoidable map artifacts (5) from model errors (17), per-category loss shares, videos and frame grids.
14. **Storage and I/O engineering on a shared GPFS fileset**: rollout-log slimming (183.91 GB to 1.97 GB, 5,611 logs, verified lossless for non-image data); node-local training pipeline (download, cache, delete raw, train) that made full-scale fine-tuning possible within the quota; trajdata cache from public tarballs (scan > 40 min to ~35 s extraction); packed Python env (build 2,533-3,198 s to 142 s extraction); fresh-part pre-fetch; symlink dedupe with sha256 verification.
15. **Exact reimplementations verified to zero error**: py123d target point (0.0 m on 205 routes); WA-JEPA cached-feature planning (0.0000 m).
16. **Closed-loop data collection and recovery labels** (DART-style perturbation, log-projected recovery labels, own-timing lateral labels, self-distillation control): a clean negative result with a mechanism (labels sit 0.1-0.2 m right of the model's line).
17. **Sampler-exact on-policy distillation (DAgger) objective** (11-13/14): the loss goes through the served plan (the 8-step Euler integral from the zero state, noise temperature 0) instead of the released flow-matching loss on random-noise paths the served plan never visits; unroll check 0.000 m, policy kept in eval mode; human recovery labels only where the ego is >= 1 m off the human path (anchor). Best variant D2o +0.0025 [-0.0015, +0.0068] on 691 fresh scenes, at-fault 4 -> 4: no significant gain; written up in the accepted report.
18. **Route leash add-on** (11-14/15): Hermite reference onto the served route + Frenet lateral clamp with a turn gate, from a reading of a leader's tag; clean negative (tight leash -0.0072, CI < 0).

---

## 8. Scale

- Duration: 2026-09-29 to 2026-11-13 (46 days; nuPlan paused 10-21 to 10-23 and 10-28 to 11-01).
- Git: **284 commits** (Sep 25, Oct 181, Nov 78); first 2026-09-29 22:00 EDT, last 2026-11-13 02:08 EST; 139 tracked files.
- Code (own, excluding vendored): 46 Python files; ~3,650 lines of fully own Python in `src/` + `tests/`, plus ~888 lines of the organisers' `driver.py` that we modified; 36 cluster job/env scripts, 1,574 lines; container recipes (7 Dockerfiles, 8 NOTICE files, prepare.sh) 502 lines. Vendored: GTRS model code 1,757 lines; NVIDIA sample files 1,294 lines (driver.py modified). `find src cluster container tests -type f | xargs wc -l` over text files gives ~46,166 lines, but that includes vendored WA-JEPA code and alpasim_grpc under `container/assets` (4.2 GB of assets incl. weights).
- LEDGER: 1,115 lines (~200 KB).
- Slurm jobs: the LEDGER names 238 distinct job ids explicitly and about 706 more through id ranges (some overlap), so roughly 700 to 900 jobs; the true total is not recorded.
- Local closed-loop scenes: 568 local nuPlan scene directories on the cluster (100 shard-001 + 468 others) plus fresh parts fetched per job; evaluation pools 300 + 261 + 193 (Oct) and 691 fresh (Nov); 440 NuRec scenes; 687 collection scenes. Rollout logs: 5,611 logs by 10-03 alone.
- Data volume: nuPlan-track dataset ~491 GB total (subsets fetched); local eval assets 173 GB; parts ~32-35 GB each; fine-tune A cache 133 GB on node-local disk; WA-JEPA features up to 201 GB per job; ftN 497,784 samples; full 123D train+val ~1,310 sensor logs (~2.5 TB raw, never stored on the fileset).
- Images built: 13 (wajepa dev, v1, v2-judge; q:1-3; n:1; n2:1; n3:1; w1:1; w1n:1; plus FlashDrive/PAI work handed off); 4 official submissions, 3 warmups from this thread.

- **Final scale (as of 2026-11-21, track closed)**: duration 2026-09-29 to 2026-11-16 (49 days incl. the report); **541.2 GPU-h** on Insomnia (sacct, incl. requeues); $0 rented compute; git **317 commits** (Sep 25, Oct 181, Nov 111), last 8c7715a 2026-11-16 17:57 EST, 158 tracked files; LEDGER 1,210 lines; 616 local run directories archived (2,461 aggregate files, 217.9 MB); 5 official entries and 4 warmups from team amanupg on nuPlan (v0.3 by the PAI thread; v6, v8, v9, v10 and warmups for WA-JEPA, v6, v9, v10 by this thread); cluster folder at deletion 1.4 TB / 756,691 files; final board 291 records, 63 teams.
- New code 11-13 to 11-16: `src/g2_dagger/entry.py` 131 lines, `src/g2_dagger/train.py` 340, `src/g2_leash/entry.py` 128, pool scripts 77, report .tex 197 lines.

---

## 9. Significance and impact

- **Final (track closed)**: official final rank 18th on nuPlan (per Aman; 18 of 63 teams by best-entry PCS, 17 of 57 non-host), final entry v10 PCS 2450 (final refit) / 2320 (11-15), +1,069 over the team's first nuPlan entry v0.3 in the final refit (1381). v10 is the unmodified released W1; our own add-ons and fine-tunes never beat it on the board or under our both-simulator gate. Peak standing: 5th among prize-eligible teams on 11-15 (not held; 10 teams' later entries and refits moved past). No final runs.
- Report accepted: the contribution on record is the negative-transfer analysis (local gains with CI > 0 that lost on the board), the NuRec-as-gate calibration (3/3 vs 0/3), the board-side control idea, and the sampler-exact DAgger objective.
- **Against baselines (BOARD, 11-12c)**: best entry v9 1971 vs the team's earlier nuPlan entry v0.3 1370 (+601) and vs the public v0.1 checkpoint ~1505 (+466). But v9 is **below** both released v0.2 checkpoints it could have used unchanged (joint64 seed 0 ~2191-2199; W1 2259). The gain over v0.3 is attributable to adopting the host's released models; our add-ons were net negative on the board each time (v6 -0.066 mean vs the public checkpoint; v8 ~-225 PCS; v9 ~-288 PCS).
- **Against other teams**: team rank 20 of 62 (19 of 56 non-host) on 11-12. Not in final-run range. Plain W1 (planned v10) would place near the host's 2259, about 4th among non-host teams on that snapshot.
- **Against the host**: our harness reproduces the host's published W1 results exactly; our local evaluation infrastructure matches theirs.
- **What generalises (honestly, small n)**:
  - Public navtest flatters NAVSIM-trained/tuned models; local scene score cannot rank model families (6-driver calibration, 10-02/03; then v6).
  - Local nuPlan closed loop was anti-predictive for situational add-ons on the board, 0 of 3 directions (W1 vs j64s0 ranking, v8, v9); NuRec, a different simulator with longer scenes and more decision points, was 3 of 3 (weak, n = 3). This matches the host's own research-log rule (a change must help on both nuPlan and NuRec).
  - A held-out/fresh split inside the same public benchmark does not protect against benchmark-level bias; it only protects against overfitting to scenes.
  - Situational "go" rules can raise the mean on short (~5 s) scenes while adding at-fault incidents on longer scenes with mid-scene stops, which an IRT metric punishes heavily.
  - Released checkpoints' board results (host READMEs) are the most reliable selection signal available; local results on public scenes ranked them wrongly.
- **For the PAI thread and lessons file**: wait-then-go mechanism; navtest-flatters-NAVSIM lesson; quota-measurement rule; board-control idea.

---

## 10. Research done

- **Papers / models evaluated or read**: WA-JEPA (arXiv 2608.20974, code @ bec2966, weights @ 15c0770e); Drive-JEPA (arXiv 2601.22032; weights borrowed; no closed-loop run recorded); AD-E2E-JEPA (arXiv 2609.34085; Zhu, Zhang, LeCun, Choromanska); Auto-JEPA (arXiv 2607.29031); V-JEPA 2 / 2.1 (Meta, MIT); NAVSIM (navtrain/navtest splits, command label definition); GTRS / GTRS-Dense and SimScale (OpenDriveLab); DiffusionDrive; TransFuser / Latent TransFuser; py123d_garage v0.1.1 and v0.2.0/v0.2.2 (model cards, research log, submission scripts, presets `ltf_nuplan_trainval`, `nuplan_posttrain`); Qwen-Drive-1.0 (arXiv 2609.00111); Alpamayo 1.5 and Alpamayo 2 Edge / 2 Super; FlashDrive (z-lab); SimForge Pilot-4B v1.5; Drive-IRT zoib (organisers' local evaluation); DART-style perturbation (closed-loop data); WiSE-FT weight interpolation and model soups; nuPlan (Caesar et al., arXiv 2106.11810).
- **Released checkpoints surveyed**: WA-JEPA; Drive-JEPA; SimScale LTF / DiffusionDrive / GTRS-Dense; py123d v0.1 resnet34 model_0014; py123d v0.2.0: 4 variants x 3 seeds x 3 stages (12 posttrain checkpoints compared on 1,475 host-published scenes); Qwen-Drive; Alpamayo 2 Edge; SimForge Pilot-4B.
- **Challenge sources read**: HF Space (sections 03-05, final-run selection, rules on 09-30, 10-21, 10-25, 11-09), contestant guide (e2e_challenge README @ 2023534 and e121e59), terms `official-2026-08`, alpasim issues #123, #155, #157, #182, #184, #188, #189, #191, #198, #221, #232, PR #228, organiser email of 10-23.
- **Competitor analysis**: tags and metrics of Lucifer AI (WA-JEPA adapter at 0.762, then `routebridge-scale125` 0.879 / 1553, later `lf-007`, `lf-009`, `lf-010`), SymPhi (`sp-1002a` jump to 1809 from VaVAM-based entries; `sp-1029a`, `sp-1104b`), nuVAIL (possibly SNU VAIL, low-medium certainty; `nu-vail-2`, `-9`, `-36`), YAX_NAM `base0014-v1`, the four plain-joint64 teams, W1-based entries (CQUPT, 메타몽, Lucifer). Host entries 014, 092, 093 (W1), 120 (joint32 seed 2), "0062" (v0.1 nuPlan recipe at ~4x epochs, inferred). Research sweeps (parallel agents) on 10-25 and 11-12: no public method from the leaders.
- Deep-research method itself (parallel niche-source sweeps, problem-outward) came from the PAI thread's lessons; applied here on 10-25 and 11-12.

---

## 11. Mistakes, lessons, validity failures (honest)

1. **v6 (10-21), the biggest one**: I projected the NAVSIM-trained critic's local gain (+0.128) to ~0.92 official scene score even though this ledger had shown on 10-02 that navtest flatters that family. Result 0.782, below the public checkpoint and our old v0.3; one official slot spent. Lesson: never project local navtest gains of NAVSIM-trained or navtest-tuned components; name the calibration evidence for each component.
2. **v8 and v9**: two situational add-ons (start-now, nudge A) passed tuning, held-out and fresh local nuPlan with CI > 0 and zero new failures, and each lost ~225 to 288 PCS on the board. For v9, NuRec had already shown the at-fault collisions; it was submitted on Aman's explicit call. Lesson: never submit an add-on on local nuPlan gains alone; require NuRec agreement and check board-side controls.
3. **PCS proxy**: proxy-positive add-ons (idx19, start-now) were wrong on the board; the proxy validity check (11-09) failed. Recorded rather than relied on.
4. **Missed W1 for days**: the host's rank-4 entry was a released checkpoint documented in its README; I ranked checkpoints on local data (and picked joint64 seed 2, N3) until Aman pointed at it (11-09). Lesson: map every host board entry to released checkpoints early.
5. **Storage incident (10-07, my error)**: read the quota from `df -h /insomnia001` (1.7 PB filesystem) instead of the 5 TB fileset, relied on a fork session's "expanded" conclusion, and filled the department quota with a 197 GB download, risking other users' jobs. Rule recorded and used since.
6. **Dedupe race (10-18, my error)**: a run was copying metadata while I replaced it with symlinks; cancelled and deleted.
7. **Slow-down v1 compounding bug (11-12, my design error)**: a per-plan retime compounded because the model replans from the slowed speed; caught from the NuRec distance collapse, all v1 runs discarded, v2 redesigned.
8. **Shadow-trigger corridor bug (11-10)**: measured boxes against a route that starts ~40 m ahead; caught while building the nudge, counts corrected before any decision (18/23, 4/469 superseded by 14/23, 1/469).
9. **Wrong GPU type**: queued MTGS runs on A6000 (renderer needs sm 8.9/9.0); cancelled before start.
10. **Suggested a "warmup diagnostic"** (11-08) that cannot exist (warmups are unscored).
11. **Earlier wrong claim corrected by measurement**: "the organisers' route rule almost always gives STRAIGHT" (09-29) was wrong; the 10-02 audit showed it over-signals turns.
12. **Script bugs** that cost jobs: `set -e` + pipefail interactions (silent exits, watchdog kill, `ls | head`), an inline comment inside a line-continued `hf download`, a `grep "Cached"` check that failed on prefetched batches, CRLF ids, missing `APPTAINER_TMPDIR` and `ptx_cache` bind target. All fixed and scanned for across scripts.
13. **Validity discipline** (adopted from the PAI thread's 10-29 lesson): every training run since gets a validity line (loss trend, weights moved, held-out metric); every inference change an activation check; verdict wording "tested properly, no gain" vs "no gain shown, underpowered" vs "gain confirmed on held-out". Self-disclosed weakening choices (e.g. decoder round 1 moved weights only 0.0005; round 2 validation n = 72).
14. **Tuning-set overfitting caught**: stall 5 m, idx_start_penalty 15/19, seed 0+2 ensemble and the 3-seed ensemble all looked positive on tuning and failed held-out.
15. **Lessons in `LESSONS_FOR_AGENTS.md` that came from this thread**: "The car never starts ('wait, then go') found first on nuPlan by the sibling thread"; the `navtest-flatters-navsim` memory referenced under lesson 1; the fileset `df` path rule under cluster practicalities. (The lessons file attributes "on nuPlan we missed NAVSIM JEPA planners for 11 days" to nuPlan, but the memory note it came from records that miss on nuReasoning; see section 14.) Memory lessons from this thread: navtest-flatters-navsim, nuplan-single-shot, neutral-image-tags, cluster-etiquette quota rule, "other teams' unchanged-baseline entries are a free board-side control", "map host board entries to released checkpoints", "NuRec direction 3/3 vs local 0/3".

16. **DAgger round 1 overfit (11-14)**: 79 scenes x 4 epochs; held-out ADE best after epoch 1, then rising; D1 lost on 4/5 parts. Round 2 used 234 scenes and 2 epochs. Underpowered by design (time); stated in the report.
17. **D2o never got its NuRec check**: GPUs of the one type NuRec needs (R6000) were fully taken until after the deadline. The result in the report is nuPlan-only and labelled so.
18. **Route leash built on a guess from a competitor's tag name** (11-14): legitimate as a last idea, but evidence was nuPlan-only (the kind that was wrong 0/3 before); negative anyway.
19. **Forecast for plain W1 was optimistic about standing**: I said "about 4th-5th among eligible" (true at 11-15, 5th) but did not anticipate the late wave of entries; final 18th. Board refits and last-day submissions dominate standings near the top.
20. **Board noise**: the same driver (W1) scored 2320 for us and 2332 for the host in the same refit (mean 0.93955 vs 0.94369, same GT distance), so board runs are not bit-identical; differences of ~10-150 PCS between near-identical entries are within the board's own noise (intervals ~+-150).
21. **Operational**: the challenge CLI session expired (401) mid-polling (11-15) and before the report upload (11-16); switched to the public leaderboard endpoint for reads; Aman refreshed the token himself each time. The Insomnia link dropped (VPN) 11-14 ~09:00-13:30 UTC and the SSH socket 11-15 04:39 UTC (reopened with the allowed key-auth command).
22. **Credential handling**: on 11-15 Aman offered to paste a HF / CLI token into chat; I declined and he entered it in the hidden prompt. The HF token that lived on the cluster in `.cache/hf/token` should be revoked (open item for Aman).
23. **Aman's closing assessment (11-15)**: negative about the agent's judgement over the campaign ("cost me this campaign"). The concrete costly items on record are: v6 (projected a NAVSIM-family local gain against my own 10-02 evidence), v8 and v9 (add-ons shipped on local nuPlan evidence), the 11-day-late W1 discovery, and two storage incidents. Record it as is.

---

## 12. Collaboration and borrowed / shared assets

- **AlpaSim PAI thread** (`../alpasim`, alpasim-alpamayo-pai agent): borrowed read-only its simulator sandboxes, nuPlan shard-001 scenes, summary/compare scripts, driver env overlays and the v0.3 baseline results; shared one image-tag sequence (register in its LEDGER; nuPlan v4/v6/v8/v9, PAI v5/v7); storage dedupe with sha256 verification (10-18); traded findings (our time-warp breakdown and precision check for its fine-tunes; its controller-gain results; the wait-then-go pattern, which it checked on PAI); started the PAI FlashDrive bet here (code `pai_flashdrive/`, open-loop 884 ms/plan, ADE 1.09 m on A6000) and handed it over on 10-23; on 11-04, after PAI closed, it moved the shared nuPlan data, simulator sandbox/code and HF token into this folder (verified by identical smoke-sim scores). Its board context: PAI v0.3 PCS 2143 rank 2/58 (09-29); PAI final v5 2226 (v7 2151).
- **jepa-nureasoning thread**: WA-JEPA code, checkpoint and Drive-JEPA borrowed read-only (BORROWED.md); on 11-05 we gave it read-only pointers to our py123d v0.2.2 checkout, weights and env; on 11-06 it shared its decoder fine-tune on real Motional images (5 s distance MAE 5.49 to 4.98 / 5.03 m; bias at rest +2.7 / +2.3 to +0.5 / -0.9 m), which helped interpret our decoder results.
- **nureasoning thread**: its torch env (`ext/a15env`) and HF cache used read-only early on.
- **Organisers' assets**: NAVSIM sample adapter (Apache-2.0), SimScale checkpoints, MTGS assets, trajdata cache tarballs, report template (CC BY 4.0 adaptation).
- **Rule**: `../alpasim`, `../jepa-nureasoning`, `../nureasoning` read-only from here; every borrowed item listed in `BORROWED.md`; Aman approved every deletion per item and every outward-facing step (push, warmup, submit).

---

## 13. Resume bullet drafts (truthful, numbers labelled)

Keep the honest framing: the best official score came from adopting released checkpoints; our add-ons did not beat them on the board. Do not claim "beat the baseline" on the board.

### FINAL numbers to use (supersede the 11-13 bullets below where they conflict)
- Final rank 18th on the nuPlan track of the NVIDIA AlpaSim End-to-End Closed-Loop Driving Challenge 2026 (63 teams on the final board, 291 entries); final entry PCS 2450 (final board) / 2320 (at submission, 11-15); 5th among prize-eligible teams at the time of submission (11-15 board), not held at close. Technical report accepted.
- Honest framing: the final entry is the released W1 checkpoint run unmodified; our ~20 add-ons, fine-tunes and distillation variants did not beat it under a two-simulator gate, and the three we shipped (v6, v8, v9) lost on the board. The research value is the negative-transfer analysis.
- Possible bullet: "Wrote and submitted the track's technical report ('Local Gains That Did Not Transfer'), documenting three locally significant gains (+0.012 to +0.128 mean scene score, CI > 0, up to 754 paired scenes) that lost 225-288 PCS on the private board, and a second-simulator gate that called the board's direction 3/3 vs 0/3."
- Possible bullet: "Designed a sampler-exact on-policy distillation (DAgger) objective for a 67M flow-matching driving planner (loss through the 8-step served Euler integral; 0.000 m unroll check), trained 4 variants on 319 log-disjoint closed-loop scenes; best +0.0025 [-0.0015, +0.0068] on 691 held-out scenes (not significant), reported as such."
- Scale bullet: "541 GPU-hours on a Slurm cluster (L40S/L40/H100/A6000/RTX PRO 6000), ~700-900 jobs, 1,400+ local nuPlan scenes and 440 NuRec scenes; 1.4 TB working set cleaned up with a verified 1.2 GB archive."

### Short (one line each)
- Led team amanupg's nuPlan-track entry in the NVIDIA AlpaSim End-to-End Closed-Loop Driving Challenge 2026 (nuPlan track, 62 teams); best official entry PCS 1971 (team rank 20/62, 2026-11-12 board), up from the team's earlier 1370.
- Built a deterministic, paired closed-loop evaluation pipeline on a Slurm GPU cluster (~700+ jobs, 1,400+ local scenes, 440 NuRec scenes) and showed local nuPlan gains were 0/3 predictive of the official board while a NuRec cross-check was 3/3 (n = 3).
- Engineered node-local data and training pipelines that cut rollout-log storage 93x (183.91 GB to 1.97 GB) and environment start-up from 42-53 min to ~2.4 min on a shared GPFS fileset.

### Research angle (longer)
- Investigated world-model (WA-JEPA, 788M-param V-JEPA 2.1-based) and Latent TransFuser planners for closed-loop driving in NVIDIA AlpaSim; WA-JEPA beat our Alpamayo-1.5 entry by +0.198 [+0.131, +0.265] mean scene score locally (100 scenes; +0.219 on a held-out shard), but a calibration of six drivers against official results showed public navtest inverts the official ranking of NAVSIM-trained models, which drove a pivot to route-conditioned Latent TransFuser checkpoints.
- Diagnosed a receding-horizon "wait-then-go" failure (the planner re-plans a 1.7-4.0 s wait at every step, so the car never starts) from plan logs; a rule fix gained +0.015 [+0.009, +0.021] over 754 local scenes with CI > 0 on tuning, held-out and fresh sets, yet cost ~225 PCS on the private board, a documented case of benchmark-level bias that held-out splits cannot catch.
- Ran 3 closed-loop fine-tuning variants of a 68M flow-matching planner's decoder on 687 self-collected perturbed scenes plus a self-distillation control, isolating that log-derived lateral labels (biased 0.1-0.2 m from the model's line) caused added off-road failures (-0.023 [-0.042, -0.004] vs control).
- Built a local refit of the challenge's item-response ranking metric (Drive-IRT zoib) and validated it against the board, finding it could not detect a situational add-on's private-set failure; adopted a second simulator (NuRec) as the decision gate after it matched the board's direction 3 of 3 times (local nuPlan 0 of 3).

### Engineering angle
- Shipped 4 official and 3 warmup submissions as offline, read-only Docker images (5.6 to 12.8 GB, <= 16 GiB VRAM, 1,145-1,235 s of a 3,000 s budget on 1,000 rollouts), each re-verified bit-identical in closed loop from the exact archive (200/200 scenes) with sha256 checks of weights and code inside the image.
- Wrote add-on drivers that wrap the host's gRPC driver without modifying it (critic substitution, stall rescue, time warp, start-now, stall nudge, speed cap), a shadow-mode logger of the model's own detections and drivable-area predictions, and a firing-set paired design that limits evaluation to scenes a rule can affect (40 of 552 scenes; 167-188 instead of 1,764 NuRec scene-runs).
- Reproduced the host team's published per-scene results exactly (182/200 identical, mean diff 0.0000) and their route target-point computation to 0.0 m on 205 routes.

### ML-infra angle
- Operated Slurm on a shared university cluster across L40S, L40, H100, A6000 and RTX PRO 6000 Blackwell GPUs: node-local download/cache/train pipelines (430-log fine-tune: 133 GB cache, 25,395 steps in 68 min at ~485 samples/s on one Blackwell GPU), Apptainer sandboxes from Docker archives, renderer-architecture-aware scheduling (MTGS sm 8.9/9.0, NRE OptiX 9 needing driver R570+), faulty-node exclusion (ECC, CUDA, launch failures) and backfill-friendly limits (23 sims in ~3 h at the lowest fair share).
- Fixed shared-filesystem bottlenecks: lossless rollout-log slimming (5,611 logs, 183.91 GB to 1.97 GB, verified per file), cache-from-tarball extraction (> 40 min scan to ~35 s), packed Python environments (2,533-3,198 s build to 142 s), parallel part pre-fetch, symlink dedupe with full sha256 verification.

### Interview talking points
- Why WA-JEPA looked great locally (0.958) and was weak officially (another team's adapter 0.762 / PCS 1022): NAVSIM-trained models are tuned on the very public scenes used for local evaluation; how I found it (six-driver calibration) and what it changed.
- The v6 failure: a +0.128 local gain that became -0.066 officially; what I should have weighted (my own 10-02 evidence), and the rule I adopted.
- The wait-then-go mechanism: why a receding-horizon MPC tracking only 2.5 s of a "wait then go" plan never starts the car; why fixing it helped on 5 s scenes and hurt on 20 s scenes with mid-scene stops (at-fault front collisions ~2 s after acting).
- Item-response metrics: why many small wins can lose rank if a few scenes that strong entries pass go to zero; building and falsifying a local proxy.
- Determinism and noise: MTGS bit-exact on one GPU type (A/A 280/300 identical across GPU types, ~0.006 noise floor), NuRec not repeatable (paired reruns needed), and the firing-set design that follows from "a rule cannot change a scene before it acts".
- Shadow mode: designing triggers from the model's own perception offline; why the off-road guard was rejected (map cannot resolve sub-metre curb drift).
- Honest negatives: WA-JEPA route conditioning (6 runs), py123d fine-tunes on top of the critic, v0.2 fine-tune and every inference knob, closed-loop decoder fine-tuning, ensembles, slow-down, controller gains.
- What I would do differently: get board-side controls and released-checkpoint board mappings in week one; treat a second simulator as the gate for any situational rule; spend official slots on whole-policy changes with board evidence.

---

## 14. Open questions and uncertain numbers (flagged, not guessed)

1. **Board rank field vs PCS**: in snapshot 1112c, Lucifer lf-009 has rank 1 with PCS 2273 while three entries with higher PCS (2286-2288) have ranks 2-4. The `rank` field appears not to be plain PCS order (perhaps a posterior rank statistic). Team rank 20 was computed by best-entry PCS; by the rank field it is also 20.
2. **Field size**: 62 distinct team ids in 1112c (6 host-labelled); the LEDGER's 11-12 read said 60 teams (240 entries). Both are correct for their snapshots.
3. **Deadline**: Nov 16 AoE (LEDGER, organiser email) vs "Nov 17 12:10 UTC" in a memory note; AoE end of Nov 16 is Nov 17 ~12:00 UTC. Confirm on the Space.
4. **Board refits**: every PCS changes with refits (e.g. v8 1854 to 1903 to 1928; host W1 2181 to 2247 to 2259). Any resume number should name its date. Mean scene scores of v0.3 and v6 changed too (likely the 10-22 corridor re-evaluation; not verified).
5. **Cause of the v8/v9 board losses**: NuRec and the incident metrics point to the add-ons acting where waiting was right; an image difference was ruled out for v9 (200/200 identical) but not formally for v8 vs other teams' joint64 images.
6. **Turns-only speed cap (SC)**: neutral on nuPlan (691); NuRec untested because both R6000 nodes were drained as of 11-13 ~01:30.
7. **The first nuplan-warmup (2026-09-27)**: image not recorded in this thread. Also which earlier September tags (`v0.1-starter`, `v0.2-a15int8`) were nuPlan vs PAI submissions is not recorded here; only v0.3 appears on the nuPlan board.
8. **Warmup date for the WA-JEPA image**: LEDGER records it as 2026-10-02 05:47-05:55 UTC in one entry and "warmup succeeded on 2026-10-03" in others; the UTC times favour Oct 2.
9. **WA-JEPA checkpoint size**: BORROWED.md lists `model_state_dict.pt` as 1.5 GB, while the ledger computed ~3.2 GB at fp32 for 788 M parameters; storage dtype not checked.
10. **`local/w1:1` image size**: `docker images` showed 36.1 GB, which earlier proved a display artefact for q:2/q:3 (12.79 GB actual); not re-measured.
11. **Optimiser and batch size** of our py123d fine-tunes and decoder runs are the py123d defaults and are not written in the LEDGER; decoder batch ~32 is inferred from steps, not recorded.
12. **Aggregate GPU-hours and job counts** are not recorded; section 8 gives a range from job ids.
13. **Lateral label bias** (labels 0.1-0.2 m right of the model's line): human line vs reference-point/frame offset, unresolved.
14. **Frozen traffic light in NuRec/MTGS renders** suspected in a W1 failure video, not verified.
15. **The host's "0062" checkpoints** = nuPlan-only recipe at ~4x epochs: inference from names and configs, not confirmed.
16. **Lucifer AI `routebridge-scale125`** = route bridge + 1.25 time scale: inference from a tag only.
17. **Licence questions left to Aman**: the py123d HF checkpoint licence changed to CC BY-NC-SA 4.0 on 10-29 (our images use revision 56edbe90 from 10-21, Apache-2.0 at the time, stated in NOTICE); nuPlan data CC BY-NC-SA vs the Apache-2.0 grant to NVIDIA (shared by all nuPlan teams).
18. **Lessons-file attribution**: `LESSONS_FOR_AGENTS.md` says "On nuPlan we missed NAVSIM JEPA planners for 11 days"; the source memory note (`survey-released-checkpoints`) records that miss on nuReasoning (Drive-JEPA zero-shot). Treat it as a nuReasoning lesson.
19. **Drive-JEPA**: listed in BORROWED.md as a second candidate, but no Drive-JEPA run appears in this thread's LEDGER.
20. **Technical report**: the draft (`report/amanupg_nuplan_report.tex`, 10-21) describes v6 and has TODOs (author line, contact, official result, latency, citations). Whether a report for the final entry will be written and submitted is open.
21. **Workshop/organiser naming** (NeurIPS 2026 "World Models in Physical AI" workshop; KE:SAI, HKU OpenDriveLab) is taken from the brief; the LEDGER itself names the HF Space, NVlabs/alpasim and kesai-labs but not the workshop.
22. **Final rank framings (CONFLICT, kept open):** Aman's official final rank is **18th on nuPlan**; the final board (read 11-21) agrees by team best-entry PCS (18 of 63). Other true framings: 17th of 57 non-host teams; 5th among prize-eligible teams on the 11-15 10:36 UTC board (LEDGER line 1198, the figure in my memory notes and the Nov 15 summary); entry rank field 13 (11-15) and 37 [6-60] (final). Use 18th as the official one; the "5th eligible" line is only valid with its date.
23. **Final runs**: the organisers posted 3-run-mean final runs (11-18) for 5 teams including 메타몽, whose metamong-1103a has the same mean (0.9395) and km/incident (0.841) as v10 and was 1 PCS below us on 11-15; we got none. Selection rule and cut-off time not documented by us; not verified.
24. **Which PCS to quote**: the report and LEDGER say 2320 (11-15); the final board says 2450 for the same run (refit). Name the date with any PCS.
25. **Late entries sharing numbers**: several 11-16/17 entries from different teams (Team-WAM, tongji_zero, M-Mark, tjnh, wam-cbf) show mean 0.9289 and 1.472 km; possibly one shared public base; not verified.
26. **GPU-hours source**: 541.2 GPU-h comes from sacct run by the PAI agent / Aman (11-16 15:41 EST), not re-queried by me (the cluster folder is gone; no cluster jobs allowed for this task).
27. **README.md** still shows "Status (2026-10-14)"; LEDGER and this file are current (README updated with a final-status line in the same commit as this file).
28. **v10 image size** still not re-measured (docker display 36.1 GB vs likely ~12.6-12.8 GB).
29. Resolved since 11-13: item 3 (deadline: report accepted before Nov 16 AoE), item 6 (SC NuRec: tested, no effect), item 12 (GPU-hours: 541.2), item 20 (report: written for v10, accepted).

---

## 15. Keyword list (where used)

### Technologies and platforms
- NVIDIA AlpaSim (NVlabs/alpasim, e2e_challenge): closed-loop simulator for all local nuPlan / NuRec / PAI evaluation.
- gRPC egodriver API (`alpasim_grpc` 0.54): interface our drivers and add-ons implement.
- MTGS renderer: nuPlan scene rendering (needs sm 8.9/9.0: L40S, L40, H100).
- NVIDIA NuRec / NRE renderer (OptiX 9.0, driver R570+): second simulator, 440 PAI-AV reconstructed scenes, the decision gate.
- Docker / BuildKit (linux/amd64 on a Mac): submission images v4-v10.
- AWS ECR: registry for `teams/amanupg:<tag>` pushes.
- Apptainer 1.4.5: running images and simulator sandboxes on the cluster.
- Slurm (sbatch, srun, dependencies, requeue, --test-only, partitions short/burst): ~700-900 jobs, 541.2 GPU-h.
- Columbia Insomnia HPC, GPFS fileset, node-local /local disks: all compute and storage.
- NVIDIA GPUs L40S, L40, H100, RTX A6000, RTX PRO 6000 Blackwell: sims (L40S/L40/H100), training (A6000, Blackwell), NuRec (Blackwell only).
- Hugging Face Hub (hf_xet): model weights and nuPlan-track data downloads.
- GitHub (private repo amanupg/alpasim-jepa-2026): code, LEDGER, report.
- Challenge CLI (`alpasim_challenge.py`): limits, ecr-login, submit, status, leaderboard, report upload.
- LaTeX / tectonic / TikZ: 4-page technical report.

### ML methods and models
- Latent TransFuser (LTF), py123d_garage v0.1.1 (ResNet-34) and v0.2.0/v0.2.2 (68M flow-matching): final model W1 and fine-tune bases.
- Flow matching / Euler sampling: W1's planner head; basis of the sampler-exact DAgger loss.
- WA-JEPA (V-JEPA 2.1 ViT-L + flow predictor, 788M): first nuPlan candidate, route fine-tune pilots.
- V-JEPA 2 / 2.1, JEPA world models: WA-JEPA backbone; thread's original motivation.
- Drive-JEPA: borrowed, surveyed, not run.
- GTRS-Dense critic, SimScale (OpenDriveLab): radius-limited, margin-gated plan substitution in v6.
- Alpamayo 1.5 (int8) / Alpamayo 2 Edge: team's v0.3 baseline; Edge assessed 11-13, not used.
- DiffusionDrive, TransFuser, SimWAM, ZTRS: baselines and surveyed planners.
- Fine-tuning (full, decoder-only, frozen backbone), torch.compile, bf16 mixed precision: fine-tunes A, A2, A31, ftN, CL decoder, DAgger.
- WiSE-FT weight interpolation, model soups: tried on fine-tunes, rejected.
- Seed ensembles (plan averaging): joint64 and waypoints 3-seed ensembles, rejected.
- DAgger / on-policy distillation with recovery labels, DART-style perturbation: closed-loop data collection and the 11-13/14 W1 distillation.
- Self-distillation / best-of-N self-imitation: control arm and dropped round-2 idea.
- Model predictive control (MPC) controller gains: tuned and rejected (heading, steering-change weights).
- Rule-based add-ons (start-now, stall nudge, stall rescue, time warp, speed caps, route leash, emergency brake): v6, v8, v9 and last-slot candidates.
- Item Response Theory, Drive-IRT zero-one-inflated beta (zoib): the board metric (PCS); our local proxy refit.
- Paired bootstrap confidence intervals, win/loss counts, power (half-width) analysis: every local verdict.
- Tuning / held-out / fresh log-disjoint splits: evaluation protocol.
- Firing-set paired design: evaluating situational rules only where they act.
- Shadow-mode logging of model perception (boxes, drivable area, BEV): offline trigger design.
- Failure census (zero-score vs low-progress, off-road, collision, stuck): directed every add-on.
- Board-side controls (other teams' unmodified baselines): measuring our add-ons' board effect.

### Datasets and benchmarks
- nuPlan (Motional) / OpenDriveLab AlpasimChallenge2026_nuplan_track (MTGS parts, navtest configs): local closed-loop scenes, ~491 GB public set.
- kesai-labs/nuplan (123D logs): fine-tune and decoder training data.
- NAVSIM navtest / navtrain / navhard: model provenance; source of the "navtest flatters NAVSIM models" lesson.
- NVIDIA PAI-AV NuRec scenes (441 curated val ids): second simulator.
- Private AlpaSim nuPlan test set (~1,000 scenes, 20 logs): official board only, never accessed.
- Host-published per-scene results (1,485 navtest scenes): checkpoint selection and harness reproduction.

### Tools and engineering
- Python, NumPy, PyTorch 2.8, PyTorch Lightning, timm, OpenCV, omegaconf, einops, pandas/parquet, uv: all code.
- Bash / sbatch scripting (`sim_nuplan.sbatch`, `sim_nuplan_multi.sbatch`, `sim_nurec.sbatch`, `dagger_*.sbatch`, `fetch_parts.sbatch`): evaluation and training pipelines.
- sha256 / md5 verification, image-check protocol: every submitted image and the cleanup archive.
- Rollout-log slimming, packed envs, tarball caches, parallel prefetch, symlink dedupe: storage and I/O on the shared fileset.
- Multi-agent research workflows (deep research, parallel agents) and LinkedIn/web sweeps: 10-25, 11-12, 11-13 research rounds.
- LEDGER-driven experiment tracking (1,210-line chronological ledger): ground truth for every number.

### Skills shown
- Closed-loop evaluation design and statistical validity (paired CIs, power, held-out discipline).
- Diagnosing benchmark bias / negative transfer (local vs private board, two-simulator calibration).
- Failure analysis of learned planners (wait-then-go receding-horizon diagnosis).
- ML infrastructure on a shared HPC cluster (scheduling by GPU architecture, storage limits, preemption).
- Competition operations under hard limits (3 slots/month, 40 GiB images, 16 GiB VRAM, 3,000 s budgets, licence compliance with NOTICE files).
- Technical writing (accepted challenge report) and honest reporting of negative results.
- Licence and data-rights review (Apache-2.0 vs CC BY-NC-SA relicensing, public-data-only eligibility).
