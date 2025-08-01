#!/usr/bin/bash
#SBATCH --job-name=inference-benchmark
#SBATCH --time=2-00:00:00
#SBATCH --account=<slurm-user>
#SBATCH --output=logs/inference-benchmark-%N-%j.log
#SBATCH --nodes=1
#SBATCH --mincpus=4

#-SBATCH --gres=gpu:1

HABANA_DOCKER_IMAGE=vault.habana.ai/gaudi-docker/1.21.2/ubuntu24.04/habanalabs/pytorch-installer-2.6.0
NVIDIA_DOCKER_IMAGE=nvcr.io/nvidia/pytorch:25.06-py3
ROCM_DOCKER_IMAGE=rocm/pytorch:rocm6.4.2_ubuntu22.04_py3.10_pytorch_release_2.6.0
#XPU_DOCKER_IMAGE=intel/intel-extension-for-pytorch:2.7.10-xpu --> missing libmetee
XPU_DOCKER_IMAGE=intel/intel-extension-for-pytorch:2.6.10-xpu

ARCH=$(uname -m)

function usage() {
    echo "$0 <options>"
    echo "options:"
    echo "-b    benchmark name"
    echo "-d    data directory"
    echo "-h    this help"
    echo "-i    iteractive docker session"
    echo "-w    base/working directory"
}

export BASE_DIR=$PWD
export DATA_DIR=$BASE_DIR/data

while getopts "hib:d:w:" option; do
    case $option in
        b)
            BENCHMARK_NAME=$OPTARG
            export BENCHMARK_NAME
            ;;
        d)
            DATA_DIR=$(realpath -L $OPTARG)
            export DATA_DIR
            ;;
        i)
            DOCKER_INTERACTIVE="-it" 
            export DOCKER_INTERACTIVE
            ;;
        h)
            usage
            exit 0
            ;;
        w)
            BASE_DIR=$(realpath -L $OPTARG)
            export BASE_DIR
            ;;
        *)
            ;;
    esac
done

SCRIPT_DIR=$(realpath -L $(dirname $0))
export BENCHMARKS_D_DIR=$SCRIPT_DIR/benchmarks.d
if [ -z "$BENCHMARK_NAME" ]; then
    echo "Please specify a benchmark to run using -b option. Available are:"
    ls $BENCHMARKS_D_DIR | sed 's/\.sh//g'
    exit 0
fi

function user_command() {
    BENCHMARK_SCRIPT="$BENCHMARKS_D_DIR/$BENCHMARK_NAME.sh"
    if [ ! -e "$BENCHMARK_SCRIPT" ]; then
        echo "echo Missing implementation script: $BENCHMARK_SCRIPT"
        exit 10
    fi

    CMD="/workspace/benchmarks.d/${BENCHMARK_NAME}.sh $@"
    if [ -n "$DOCKER_INTERACTIVE" ]; then
        echo "bash"
    else
        echo "bash -c $CMD"
    fi
}

## BEGIN MAIN
module load docker 

if ! command -v slurm-monitor; then
    if [ -d venv-$ARCH-slurm-monitor ]; then
       source venv-$ARCH-slurm-monitor/bin/activate
    fi

    if ! command -v slurm-monitor; then
        echo "'slurm-monitor' is not installed. Please create a python virtual env and run"
        echo "   pip install git+https://github.com/2maz/slurm-monitor"
        exit 10
    fi
fi


# The benchmark log files will be saved to deeplearning-benchmark/pytorch/results/$NAME_TYPE_1xA100_80GB_$(hostname)
export NAME_TYPE=cluster


# Test for this many GPUs
export GPU_COUNT=${GPU_COUNT:-1}
echo "GPUs available: $(slurm-monitor system-info -q gpus.count), benchmarking: $GPU_COUNT"
export GPU_NAME=`echo "$(slurm-monitor system-info -q gpus.model)" | tr ' ' '-' | tr '[]()' '-'`
export GPU_SIZE=`echo $(slurm-monitor system-info -q gpus.memory_total)/1024^3 | bc`
export GPU_FRAMEWORK=`slurm-monitor system-info -q gpus.framework`

CPU_COUNT=`echo "2*$GPU_COUNT" | bc`
echo "CPUS used: $CPU_COUNT"

export DL_BENCHMARK_DIR=$BASE_DIR/naic-deeplearning-benchmark/pytorch
export DL_EXAMPLES_DIR=$BASE_DIR/naic-DeepLearningExamples

export RESULTS_DIR=$SCRIPT_DIR/results/

### Run benchmark
if [ ! -d $RESULTS_DIR ]; then
    mkdir -p $RESULTS_DIR
fi

DOCKER_VOLUMES="-v ${DL_EXAMPLES_DIR}/PyTorch:/workspace/benchmark "
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${BASE_DIR}/benchmarks.d:/workspace/benchmarks.d"
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${DATA_DIR}:/data"
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${DL_BENCHMARK_DIR}/scripts:/scripts"
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${RESULTS_DIR}:/results"

DOCKER_ENVIRONMENT="-e GPU_COUNT=$GPU_COUNT"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e GPU_SIZE=$GPU_SIZE"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e GPU_NAME=$GPU_NAME"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e NAME_TYPE=$NAME_TYPE"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e NODE=$(hostname)"


echo "DOCKER_ENVIRONMENT: $DOCKER_ENVIRONMENT"

if [ "$GPU_FRAMEWORK" == "rocm" ]; then
    if [ -n "$CUDA_VISIBLE_DEVICES" ]; then
        DOCKER_CUDA_SETUP="-e CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES "
    fi
    docker run \
        $DOCKER_INTERACTIVE \
        $DOCKER_CUDA_SETUP \
        $DOCKER_VOLUMES \
        $DOCKER_ENVIRONMENT \
        --rm --shm-size 8G  \
        --cap-add=SYS_PTRACE \
        --security-opt seccomp=unconfined \
        --device=/dev/kfd \
        --device=/dev/dri \
        --group-add video \
        --ipc=host \
        $ROCM_DOCKER_IMAGE \
        $(user_command)
elif [ "$GPU_FRAMEWORK" == "cuda" ]; then
    if [ -n "$CUDA_VISIBLE_DEVICES" ]; then
        # Use the device UUIDs to avoid ambiguities
        DEVICE_UUIDS=$(nvidia-smi --query-gpu=uuid --format=csv,noheader | tr '\n' ',' | sed 's/,$//')
        DOCKER_CUDA_SETUP="--gpus device='\"$DEVICE_UUIDS\"'"
    else
        DOCKER_CUDA_SETUP="--gpus all"
    fi
    USER_COMMAND=$(user_command)
    docker run \
        $DOCKER_INTERACTIVE \
        $DOCKER_CUDA_SETUP \
        $DOCKER_VOLUMES \
        $DOCKER_ENVIRONMENT \
        --rm --shm-size=1024g \
        --cpus $CPU_COUNT \
        $NVIDIA_DOCKER_IMAGE \
        $(user_command)
elif [ "$GPU_FRAMEWORK" == "habana" ]; then
    if [ $GPU_COUNT -eq 1 ]; then
        DOCKER_CUDA_SETUP="-e HABANA_VISIBLE_DEVICES=0"
    else
        DOCKER_CUDA_SETUP="-e HABANA_VISIBLE_DEVICES=all"
    fi
    echo "$(user_command -d hpu -i 100 -n 100)"
    docker run \
        $DOCKER_INTERACTIVE \
        $DOCKER_CUDA_SETUP \
        $DOCKER_VOLUMES \
        $DOCKER_ENVIRONMENT \
        --rm \
        --runtime=habana \
        -e OMPI_MCA_btl_vader_single_copy_mechanism=none \
        --cap-add=sys_nice \
        --shm-size=32g \
        --net=host \
        $HABANA_DOCKER_IMAGE \
        $(user_command -d hpu -i 100 -n 100)
elif [ "$GPU_FRAMEWORK" == "xpu" ]; then
    docker run \
        $DOCKER_INTERACTIVE \
        $DOCKER_VOLUMES \
        $DOCKER_ENVIRONMENT \
        --rm \
        --device /dev/dri \
        -v /dev/dri/by-path:/dev/dri/by-path \
        --ipc=host \
        $XPU_DOCKER_IMAGE \
        $(user_command -d xpu -i 1 -n 1)
else
    echo "Unsupported framework: $GPU_FRAMEWORK"
fi
