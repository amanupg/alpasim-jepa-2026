#!/bin/bash
#SBATCH -A edu
#SBATCH -p short,burst
#SBATCH -J aj_sbx
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH -t 01:00:00
#SBATCH -o /insomnia001/depts/edu/users/au2327/alpasim-jepa/logs/build_sandbox_%j.out
# Docker archive (docker save) -> apptainer sandbox, to run the submission image in the local closed loop.
#   TAR=cache/images/<name>.tar  OUT=sandbox/<name>
source /etc/profile
module load apptainer/1.4.5
set -eo pipefail
B=/insomnia001/depts/edu/users/au2327/alpasim-jepa; cd $B
export APPTAINER_CACHEDIR=$B/cache/apptainer APPTAINER_TMPDIR=${TMPDIR:-/tmp}
rm -rf $OUT; mkdir -p $(dirname $OUT)
apptainer build --sandbox $OUT docker-archive://$B/$TAR
du -sh $OUT; ls $OUT/app
