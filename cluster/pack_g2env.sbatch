#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_g2pack
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH -t 02:30:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/g2pack_%j.out
# Builds the py123d_garage v0.2.2 env once (cluster/garage2_env.sh, CPU only) and packs it into cache/g2env_v1_<key>.tar,
# which later jobs extract node-local instead of rebuilding from the GPFS uv cache.
source /etc/profile
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa
G2_PACK=1 source $B/cluster/garage2_env.sh || exit 5
ls -la $B/cache/g2env_v1_*.tar
