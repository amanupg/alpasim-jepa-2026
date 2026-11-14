# nuPlan last slot: what I tried (Nov 12 to Nov 14)

**Result: nothing beat plain W1. Recommendation: submit plain W1 (`local/w1:1`) as `v10`, warmup first.**

The gate for any change was the same throughout: it had to be better than W1 on the fresh nuPlan scenes
(interval above zero, no new at-fault collisions) and also on the 440 NuRec scenes. NuRec is the check that
called the board's direction right 3 times out of 3. Local nuPlan got it right 0 times out of 3.

## Inference-time changes (Nov 12-13)
| Try | Result | Verdict |
|---|---|---|
| 3-seed plan ensemble | NuRec -0.023, 25 wins / 57 losses (147 scenes) | failed |
| Blend action and waypoint outputs | not possible: W1 has no action head | n/a |
| Emergency brake using the model's detected boxes | early enough in 10/19 NuRec collisions offline, 0/3 on nuPlan (boxes missed the cars) | not built |
| Speed cap 0.9 | nuPlan -0.013, 2 wins / 89 losses (500 scenes) | failed |
| Speed cap 0.8 in turns only | nuPlan +0.000 (691), NuRec +0.000 (440) | no effect |
| Speed cap 0.6 in turns only | NuRec at-fault 61 -> 52, but nuPlan -0.008 (4 wins / 43 losses) | failed |
| Controller gains (heading 2.0, steering-rate 2.5) | -0.005 and -0.003, 1-2 new zero-score scenes | failed |

My first slow-down version had a compounding bug: the slower speed fed back into the next plan. I threw away
those runs and fixed the design before the cap results above.

## Research (Nov 13)
- Deep research sweep, a LinkedIn sweep and Alpamayo 2 Edge: nothing usable before the deadline. Alpamayo 2 Edge
  has no nuPlan numbers, expects 6 cameras (nuPlan gives 3), is slow per plan, and its licence fit is unclear.
- KE:SAI's on-policy distillation is announced but not released. That gave me the idea for the last experiment.

## Last experiment: on-policy distillation (DAgger) of W1's decoder (Nov 13-14)
- W1 drove 234 training scenes, some with deliberate noise added to its plans, and I recorded where it ended up.
  Each state it reached was labelled with the human driver's recovery back to the logged path. The training
  scenes share no log with the 691 test scenes.
- New training loss: it goes through the exact plan W1 serves (8 deterministic steps from zero noise). The
  released loss trains on random-noise paths that the served plan never uses.
- A second idea, keeping the best-scoring noisy rollout per scene, had no signal. Noise improved only 1 of 79
  scenes and fixed none of W1's failures.

| Variant | 691 fresh scenes vs W1 | Wins / losses | At-fault collisions |
|---|---|---|---|
| D1 human labels everywhere | -0.036 [-0.053, -0.019] | 68 / 113 | 4 -> 9 |
| D1o human labels only >= 1 m off the human path | -0.004 [-0.008, -0.000] | 49 / 38 | 4 -> 5 |
| D2h human labels only >= 0.5 m off, more data | -0.005 [-0.011, -0.000] | 50 / 39 | 4 -> 5 |
| **D2o human labels only >= 1 m off, more data** | **+0.003 [-0.002, +0.007]** | **64 / 22** | **4 -> 4** |

D2o is the only one that did no harm. Its gain is too small to tell apart from zero on 691 scenes, so it does
not pass. I queued its NuRec run for the report, but it cannot start before the deadline. One R6000 node is
fully busy and the other has all its memory taken; Slurm estimates Nov 20.

## Board (Nov 14, 14:23 UTC)
- Best per team: CQUPT 2359, SymPhi 2359, nuVAIL 2353, Lucifer 2336, organisers' W1 entry 2317, 메타몽 2303.
- Ours: v9, 1994.
- Plain W1 should land near the organisers' W1 entry, about 5th among prize-eligible teams. The leaderboard prize
  goes to 1st only.

## Your steps for v10 (I don't push or submit)
1. Refresh the CLI token with the hidden prompt (`configure-token`). The session expired, so `limits` returns 401.
2. Run `limits`. Expect 1 official and 1 nuplan-warmup left.
3. Push `local/w1:1` (digest db5833d6...) as `v10`.
4. Submit the nuplan-warmup, then the official run if the warmup succeeds.
5. Deadline: Nov 16 AoE, about Nov 17 12:00 UTC.

## Report
- Draft: `report/amanupg_nuplan_report_final.tex` and `.pdf`, 4 pages, for you to check. Not uploaded.
- Its main point is that local nuPlan gains did not transfer to the board, while NuRec and other teams' unchanged
  baselines did predict it. It also covers the start-from-rest diagnosis and sampler-exact DAgger.
- TODOs: your name, organisation and email; the official v10 numbers.
