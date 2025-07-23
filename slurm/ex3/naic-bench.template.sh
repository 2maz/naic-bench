#!/bin/bash
#SBATCH --account=ACCOUNT
#SBATCH --job-name=naic-bench-NODENAME
#SBATCH --output=/global/D1/projects/NAIC/logs/naic-bench-NODENAME-%j.log
#SBATCH --time=0-20:00:00
#SBATCH --partition=PARTITION
#SBATCH --nodelist=NODENAME
#SBATCH --ntasks=1
#SBATCH --gres=gpu:GPU_COUNT

echo "Starting job at time:" && date +%Y-%m-%d_%H:%M:%S
set -x
module load docker

NAIC_BASE_DIR=/global/D1/projects/NAIC
DATA_DIR=$NAIC_BASE_DIR/data/lambdal

cd $NAIC_BASE_DIR/software/naic-bench/lambdal

./prepare-slurm-monitor.sh
. venv-$(uname -m)-slurm-monitor/bin/activate

GPU_COUNT=$(slurm-monitor system-info -q gpus.count)
export GPU_COUNT

echo "Using all $GPU_COUNT available GPUs"
./run.sh -d $DATA_DIR -w test/ -b lambdal -i


