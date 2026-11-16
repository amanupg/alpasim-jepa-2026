# alpasim-jepa on Insomnia: what to keep, what to delete (2026-11-16)

Scope: `/insomnia001/depts/edu/users/au2327/alpasim-jepa` only (1.4 TB, 756,691 files). Scanned with `du` in Slurm
job 13924483. The other folders (jepa-nureasoning, nureasoning, wearable, home) are covered by the PAI agent's
scan (job 13924487). **Nothing has been deleted.**

KITScenes context (from the fork's `kitscenes-longtail/notes/assessment_2026-11-15.md`): the open track is World
Modeling, which needs 5 s of video for all 6 cameras plus an optional trajectory. KITScenes uses its own camera
rig and data, and has no simulator. So nuPlan/NuRec data, simulator containers and nuPlan run outputs have no
use there. A planner could only matter for the optional trajectory, and the nuReasoning Edge fine-tune is the
stronger candidate for that.

## Summary

| | Size | Action |
|---|---|---|
| Copy to the Mac first, then delete on the cluster | ~0.6 GB | per-scene results, D2o and W1 weights, 3 code files, pool scripts |
| Delete (public or rebuildable, no KITScenes use) | ~1.39 TB | data, runs, containers, caches, envs |
| Credential file | 31 MB dir | delete; the HF token in it should be revoked anyway |

After the copy, the whole `alpasim-jepa` folder can be deleted. The report and repo can be rebuilt from the Mac
copy plus the GitHub repo `amanupg/alpasim-jepa-2026`.

## Folder by folder

| Path | Size | What it is | Report needs it? | KITScenes use? | Call |
|---|---|---|---|---|---|
| `data/fs/nre-artifacts` | 751 GB | NuRec scene reconstructions (440 scenes), public NVIDIA download | no (results already pooled) | no, different rig and data | **delete** |
| `data/mtgs_parts` | 274 GB | nuPlan MTGS asset tarballs, public OpenDriveLab | no | no | **delete** |
| `data/nuplan_track` | 211 GB | navtest assets + nuplan_test configs, public OpenDriveLab | no | no | **delete** |
| `data/dagger` | 9.1 GB | our DAgger rollouts and labels (17 shards) | no (numbers in the report and LEDGER) | no | **delete** |
| `data/nuplan_cache_hf` | 2.1 GB | public nuplan_test tarball | no | no | **delete** |
| `data/py123d`, `data/nurec_curated_val_ids.txt` | 0.2 GB | nuPlan configs, scene id list | no | no | **delete** (id list is in the repo) |
| `runs/*/aggregate` (616 runs) | 0.29 GB | per-scene metrics (parquet, txt, json) behind every number in the LEDGER and report | **yes**, for any recheck or a longer write-up | no | **copy to Mac**, then delete |
| `runs/dagger_models/D2o` | 0.26 GB | our best DAgger decoder (only one with no harm) | yes, if anyone wants to reproduce Table 2 | no | **copy to Mac**, then delete |
| rest of `runs` (682 dirs) | ~98 GB | rollout videos, logs, other DAgger/critic checkpoints | no | no | **delete** |
| `weights/py123d/v0.2.0/ltf-base-waypoints-68M/posttrain` | ~0.27 GB | W1 = our final entry, Apache-2.0 at HF revision 56edbe90 (repo relicensed CC BY-NC-SA on 10-29) | yes, it is the submitted model | weak: a camera-only nuPlan planner, would need a KITScenes adapter; the Edge fine-tune is better | **copy to Mac** (the licence of this exact copy is worth keeping), then delete |
| rest of `weights/py123d` | ~3.8 GB | joint64 and streaming checkpoints, resnet34 | no | no | **delete** (public on HF) |
| `weights/wa-jepa` | 1.5 GB | WA-JEPA checkpoint, Apache, public on HF | no | listed as a candidate by the fork, but a Mac copy exists in `jepa-nureasoning/weights/wa-jepa` | **delete** |
| `weights/simscale` | 0.7 GB | organisers' sample-driver checkpoints, public | no | no | **delete** (2 of 4 already on the Mac) |
| `sandbox/alpasim-base` | 20 GB | AlpaSim Apptainer sandbox | no | no simulator in KITScenes | **delete** |
| `sif/nre-ga_26.04.sif` | 12 GB | NuRec renderer container, public NGC | no | no | **delete** |
| `cache` (uv 17 GB, g2env tar 8.2 GB, other) | 25 GB | package caches, packed garage env | no | no | **delete** |
| `envs` (garage 8.2 GB + overlays) | 8.7 GB | Python env for py123d_garage | no | only if W1 is ever tried on KITScenes; rebuildable in ~20 min | **delete** |
| `ext` | 79 MB | public code checkouts (alpasim, py123d_garage, WA-JEPA, flashdrive) | no | no | **delete** (also on the Mac) |
| `logs` | 154 MB | Slurm logs | no | no | **delete** |
| `src`, `cluster`, `container`, `tests`, `staging_dagger`, `pai_flashdrive` | 2 MB | our code; all in the GitHub repo except 3 files | the 3 files below | no | copy `cluster/audit_cmp.sbatch`, `src/tools/compare_runs.py`, `src/tools/summarize_run.py`, then **delete** |
| `tmp` | 16 MB | pooling scripts (`pool_fresh.py`, `pool_nurec.py`, `pool_dagger.py`), inventory output | the scripts | no | copy the scripts into `analysis/`, then **delete** |
| `.cache` | 31 MB | HF token file (mode 600) and HF cache | no | no | **delete**; revoke that token on HF |

## Also ours, outside this folder (in the PAI agent's scan)
- `~/.cache/nre` in home (1.4 GB): NuRec renderer cache from our runs. Deletable.

## Order if Aman approves
1. Copy to the Mac: `runs/*/aggregate` (without the png files), `runs/dagger_models/D2o`, the W1 posttrain folder,
   the 3 code files and the pool scripts. Check file counts and checksums.
2. Commit the code and scripts to the repo; keep the results and weights on the Mac outside git.
3. Delete the folder in one step, after a final `ls` and Aman's per-item OK (he may approve the whole folder at once).
