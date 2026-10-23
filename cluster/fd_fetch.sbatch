#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_fdfetch
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 03:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/fd_fetch_%j.out
# FlashDrive weights (Aman 2026-10-23, PAI bet): z-lab/Alpamayo-1.5-10B (base; its expert shard differs from
# nvidia's by hash, so it is not substituted) and z-lab/Alpamayo-1.5-10B-PARO (W4A8 language model). The DFlash draft
# is not needed (forced <traj_future_start>, no text decoding). ~34 GB into weights/flashdrive.
source /etc/profile
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; W=$B/weights/flashdrive; mkdir -p $W
df -h /insomnia001/depts/edu/users/au2327 | tail -1
# token file path only (approved 2026-10-10; read in place, never on the command line)
export HF_TOKEN_PATH=/insomnia001/depts/edu/users/au2327/alpasim/.cache/hf/token HF_XET_HIGH_PERFORMANCE=1 HF_HUB_DISABLE_TELEMETRY=1 HOME=$TMPDIR
for r in Alpamayo-1.5-10B Alpamayo-1.5-10B-PARO; do
  t0=$(date +%s)
  $B/envs/garage/bin/hf download z-lab/$r --local-dir $W/$r > /dev/null
  echo "$r: $(du -sh $W/$r | cut -f1) in $(( $(date +%s) - t0 )) s"
done
cd $W && sha256sum */*.safetensors | cut -c1-16,65- | tee $W/sha256_prefix.txt
df -h /insomnia001/depts/edu/users/au2327 | tail -1
