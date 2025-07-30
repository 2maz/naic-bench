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
module load singularity-ce

NAIC_BASE_DIR=/global/D1/projects/NAIC
NAIC_DATA_DIR=$NAIC_BASE_DIR/data/lambdal
NAIC_BENCH_LOGS_DIR=$NAIC_BASE_DIR/software/naic-bench/logs

cd $NAIC_BASE_DIR/software/naic-bench/lambdal

./prepare-slurm-monitor.sh
. venv-$(uname -m)-slurm-monitor/bin/activate

GPU_COUNT=$(slurm-monitor system-info -q gpus.count)
export GPU_COUNT

# Select benchmark to avoid running all, e.g.,
#     PyTorch_base_base_squad_FP16
BENCHMARK=${BENCHMARK:-all}

echo "Using all $GPU_COUNT available GPUs"
echo "Running BENCHMARK=$BENCHMARK"

cd $NAIC_BASE_DIR/software/naic-bench

# NVIDIA SPECIFIC
if [ -e naic-benchmark.nvidia-$(uname -a).sif ]; then
    singularity exec -B $NAIC_DATA_DIR:/data --nv naic-benchmark.nvidia-$(uname -a).sif bash -c "cd /naic-workspace; ./resources/naic-bench/lambdal/benchmarks.d/lambdal.sh -r -t $BENCHMARK -d cuda -n 1 -o $NAIC_BENCH_LOGS_DIR -l ex3"
else
    echo "singularity image naic-benchmark.nvidia-$(uname -a).sif is not available (current dir: $PWD)"
fi


