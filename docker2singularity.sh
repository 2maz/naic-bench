#!/usr/bin/bash
set -ex

module load docker
module load singularity-ce

SCRIPT_DIR=$(realpath -L $(dirname $0))

ARCH=$(uname -i)
GPU_FRAMEWORK=nvidia

function docker_build {
    suffix=$1
    if [ ! -e Dockerfile.$suffix ]; then
        echo "Failed to locate Dockerfile.$suffix"
        exit 10
    fi
    
    echo >&2 "Building docker image for $suffix-$ARCH"
    DOCKER_IMAGE_NAME=naic/benchmark-$suffix-$ARCH
    docker build --no-cache -t $DOCKER_IMAGE_NAME -f $SCRIPT_DIR/Dockerfile.$suffix .
}

function docker_prepare_benchmarks {
    suffix=$1
    echo >&2 "Update docker base image: preparing benchmarks"
    if [ "$suffix" == habana ]; then
        EXTRA_ARGS="--runtime=habana -e HABANA_VISIBLE_DEVICES=0"
    elif [ "$suffix" == xpu ]; then
        EXTRA_ARGS="--device /dev/dri -v /dev/dri/by-path:/dev/dri/by-path --ipc=host"
    fi

    DOCKER_IMAGE_NAME=naic/benchmark-$suffix-$ARCH
    docker run -it --name naic-prepare $EXTRA_ARGS $DOCKER_IMAGE_NAME bash -c "cd /naic-workspace; ./resources/naic-bench/lambdal/benchmarks.d/lambdal.sh -p -t all"
    if [ "$suffix" == habana ]; then
        # pin triton version
        docker run -it --name naic-prepare $EXTRA_ARGS $DOCKER_IMAGE_NAME bash -c "pip install triton==3.2.0"
    fi
    COMMIT_ID=$(docker ps -a | grep naic-prepare | cut -d' ' -f1)
    docker commit $COMMIT_ID $DOCKER_IMAGE_NAME
    docker rm naic-prepare
}

function singularity_build {
    suffix=$1

    TAR_FILE="naic-benchmark-$suffix-$ARCH.tar"
    SIF_FILE="naic-benchmark.$suffix-$ARCH.sif"

    if [ -e $TAR_FILE ]; then 
        rm $TAR_FILE
    fi

    echo >&2 "Saving docker image as tar file: $TAR_FILE"
    docker save -o $TAR_FILE naic/benchmark-$suffix-$ARCH:latest


    if [ -e $SIF_FILE ]; then
        rm $SIF_FILE
    fi
    echo >&2 "Building $SIF_FILE"
    singularity build $SIF_FILE docker-archive://$TAR_FILE

    echo >&2 "Cleaning up $TAR_FILE"
    rm $TAR_FILE 
}

while getopts "hg:dps" option; do
    case $option in
        g)
            GPU_FRAMEWORK=$OPTARG
            ;;
        d)
            BUILD_DOCKER=1
            ;;
        p)
            PREPARE_DOCKER_BENCHMARKS=1
            ;;
        s)
            BUILD_SINGULARITY=1
            ;;
        h)
            echo "usage $0"
            echo "By default go through all step to build a singularity image"
            echo ""
            echo "Options:"
            echo "    -d   build docker image (step 1)"
            echo "    -p   prepare docker benchmarks (step 2)"
            echo "    -s   build singularity image from existing docker image(step 3)"
            ;;
        *)
            ;;
    esac
done

if [ -z "$BUILD_DOCKER" ] && [ -z "$PREPARE_DOCKER_BENCHMARKS" ] && [ -z "$BUILD_SINGULARITY" ]; then
    BUILD_DOCKER=1
    PREPARE_DOCKER_BENCHMARKS=1
    BUILD_SINGULARITY=1
fi

if [ -n "$BUILD_DOCKER" ]; then
    docker_build $GPU_FRAMEWORK
fi

if [ -n "$PREPARE_DOCKER_BENCHMARKS" ]; then
    docker_prepare_benchmarks $GPU_FRAMEWORK
fi

if [ -n "$BUILD_SINGULARITY" ]; then
    singularity_build $GPU_FRAMEWORK

    echo "Run the following to start:"
    if [ "$GPU_FRAMEWORK" == "habana" ]; then
        echo "    singularity shell -B $(realpath -L $PWD/../../data/lambdal):/data -B $PWD/var-log-habana:/var/log/habana_logs naic-benchmark.$GPU_FRAMEWORK-$ARCH.sif"
    else
        echo "    singularity shell -B $(realpath -L $PWD/../../data/lambdal):/data --nv naic-benchmark.$GPU_FRAMEWORK-$ARCH.sif"
    fi
fi

