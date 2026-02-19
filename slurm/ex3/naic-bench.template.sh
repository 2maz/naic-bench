#!/bin/bash
#SBATCH --account=ACCOUNT
#SBATCH --job-name=naic-bench-NODENAME
#SBATCH --output=/global/D1/projects/NAIC/logs/naic-bench-NODENAME-%j.log
#SBATCH --time=0-20:00:00
#SBATCH --partition=PARTITION
#SBATCH --nodelist=NODENAME
#SBATCH --ntasks=1
#SBATCH --gres=gpu:GPU_COUNT

GPU_COUNT=
GPU_TYPE=

echo "Starting job at time:" && date +%Y-%m-%d_%H:%M:%S
set -x
module load singularity-ce

NAIC_BASE_DIR=/global/D1/projects/NAIC
NAIC_DATA_DIR=$NAIC_BASE_DIR/data/lambdal
NAIC_BENCH_LOGS_DIR=$NAIC_BASE_DIR/software/naic-bench/logs

cd $NAIC_BASE_DIR/software/naic-bench

. venv-naic-bench-$(uname -m)/bin/activate
naic-bench singularity --data-dir $NAIC_DATA_DIR -- naic-bench run --data-dir /data --benchmarks-dir benchmarks --gpu-count $GPU_COUNT --device-type $GPU_TYPE --output-base-dir reports-ex3/node-$(hostname)-gpu-$GPU_COUNT --recreate-venv
