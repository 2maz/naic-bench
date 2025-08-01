#!/bin/bash
#SBATCH --account=ACCOUNT
#SBATCH --job-name=naic-bench-NODENAME
#SBATCH --output=/global/D1/projects/NAIC/logs/naic-bench-NODENAME-%j.log
#SBATCH --time=0-20:00:00
#SBATCH --partition=PARTITION
#SBATCH --nodelist=NODENAME
#SBATCH --ntasks=1
#SBATCH --gres=gpu:GPU_COUNT

GPU_TYPE=${1:nvidia}

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
SIF_IMAGE_NAME=naic-benchmark.$GPU_TYPE-$(uname -m).sif

echo "Using all $GPU_COUNT available GPUs"
echo "Running BENCHMARK=$BENCHMARK"

cd $NAIC_BASE_DIR/software/naic-bench

if [ ! -e $SIF_IMAGE_NAME ]; then
    echo "singularity image $SIF_IMAGE_NAME is not available (current dir: $PWD)"
    exit 10
fi

EXTRA_ARGS=
if [ "$GPU_TYPE" == "nvidia" ]; then
    EXTRA_ARGS="--nv"
elif [ "$GPU_TYPE" == "habana" ]; then
    EXTRA_ARGS="-B /tmp/var-log-habana-logs/:/var/log/habana_logs"
fi

singularity exec -B $NAIC_DATA_DIR:/data $EXTRA_ARGS $SIF_IMAGE_NAME bash -c "cd /naic-workspace; ./resources/naic-bench/lambdal/benchmarks.d/lambdal.sh -r -t $BENCHMARK -d cuda -n $GPU_COUNT -o $NAIC_BENCH_LOGS_DIR -l ex3"

