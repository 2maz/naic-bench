#!/usr/bin/bash
#SBATCH --job-name=inference-benchmark
#SBATCH --time=2-00:00:00
#SBATCH --account=roehr
#SBATCH --output=logs/inference-benchmark-%N-%j.log
#SBATCH --nodes=1
#SBATCH --mincpus=4

#ASBATCH --gres=gpu:1

module load docker 

# The benchmark log files will be saved to deeplearning-benchmark/pytorch/results/ex3_1xA100_80GB_$(hostname)
source ~/slurm-runner/venv-$(uname -i)/bin/activate

export NAME_NGC=pytorch:24.10-py3
export NAME_TYPE=ex3

export NAME_GPU=`echo "$(slurm-monitor system-info -q gpus.model)" | tr ' ' '-' | tr '[]()' '-'`
export GPU_SIZE=`echo $(slurm-monitor system-info -q gpus.memory_total)/1024^3 | bc`
export NUM_GPU=1
export GPU_FRAMEWORK=`slurm-monitor system-info -q gpus.framework`


export NAIC_PROJECT=/global/D1/projects/NAIC/
export LAMBDAL_DATA_DIR=/global/D1/projects/NAIC/data/lambdal
export LAMBDAL_BASE_DIR=/global/D1/projects/NAIC/software/lambdal

export BENCHMARKS_D_DIR=$LAMBDAL_BASE_DIR/benchmarks.d

export DL_BENCHMARK_DIR=$LAMBDAL_BASE_DIR/deeplearning-benchmark/pytorch
export DL_EXAMPLES_DIR=$LAMBDAL_BASE_DIR/DeepLearningExamples

SCRIPT_DIR=$(realpath -L $(dirname $0))
export RESULTS_DIR=$SCRIPT_DIR/results/

### Run benchmark
if [ ! -d $RESULTS_DIR ]; then
    mkdir -p $RESULTS_DIR
fi


DOCKER_VOLUMES="-v ${DL_EXAMPLES_DIR}/PyTorch:/workspace/benchmark "
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${LAMBDAL_BASE_DIR}/benchmarks.d:/workspace/benchmarks.d"
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${LAMBDAL_DATA_DIR}:/data"
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${DL_BENCHMARK_DIR}/scripts:/scripts"
DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${RESULTS_DIR}:/results"

DOCKER_VOLUMES="$DOCKER_VOLUMES -v ${NAIC_PROJECT}:/NAIC"

DOCKER_ENVIRONMENT="-e NUM_GPU=$NUM_GPU"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e GPU_SIZE=$GPU_SIZE"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e NAME_GPU=$NAME_GPU"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e NAME_TYPE=$NAME_TYPE"
DOCKER_ENVIRONMENT="$DOCKER_ENVIRONMENT -e NODE=$(hostname)"

while getopts "ib:" option; do
    case $option in
        i)
            DOCKER_INTERACTIVE="-it" 
            export DOCKER_INTERACTIVE
            ;;
        b)
            BENCHMARK_NAME=$OPTARG
            export BENCHMARK_NAME
            ;;
        *)
            ;;
    esac
done

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
        rocm/pytorch:latest \
        $(user_command)
elif [ "$GPU_FRAMEWORK" == "cuda" ]; then
    if [ -n "$CUDA_VISIBLE_DEVICES" ]; then
        DOCKER_CUDA_SETUP="--gpus device=$CUDA_VISIBLE_DEVICES "
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
        nvcr.io/nvidia/${NAME_NGC} \
        $(user_command)

elif [ "$GPU_FRAMEWORK" == "habana" ]; then
    HABANA_IMAGE=vault.habana.ai/gaudi-docker/1.17.1/ubuntu22.04/habanalabs/pytorch-installer-2.3.1

    if [ $NUM_GPU -eq 1 ]; then
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
        $HABANA_IMAGE \
        $(user_command -d hpu -i 100 -n 100)
elif [ "$GPU_FRAMEWORK" == "xpu" ]; then
    echo "python /NAIC/software/pytorch-benchmark/inference-benchmark.py --label $NAME_GPU -o /results/inference-benchmark-$NAME_GPU.json -d xpu -i 1 -n 1"
    docker run \
        $DOCKER_INTERACTIVE \
        $DOCKER_VOLUMES \
        $DOCKER_ENVIRONMENT \
        --rm \
        --device /dev/dri \
        -v /dev/dri/by-path:/dev/dri/by-path \
        --ipc=host \
        intel/intel-extension-for-pytorch:2.3.110-xpu \
        $(user_command d xpu -i 1 -n 1)
else
    echo "Unsupported framework: $GPU_FRAMEWORK"
fi
