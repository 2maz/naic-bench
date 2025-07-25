#!/usr/bin/bash
set -ex

module load docker
module load singularity-ce

SCRIPT_DIR=$(realpath -L $(dirname $0))

ARCH=$(uname -i)
GPU_FRAMEWORK=nvidia

function build_docker {
    suffix=$1
    if [ ! -e Dockerfile.$suffix ]; then
        echo "Failed to locate Dockerfile.$suffix"
        exit 10
    fi
    
    echo >&2 "Building docker image for $suffix-$ARCH"
    docker build --no-cache -t naic/benchmark-$suffix-$ARCH -f $SCRIPT_DIR/Dockerfile.$suffix .
}

function build_singularity_image() {
    suffix=$1

    TAR_FILE="naic-benchmark-$suffix-$ARCH.tar"
    SIF_FILE="naic-benchmark.$suffix-$ARCH.sif"

    if [ -e $TAR_FILE ]; then 
        rm $TAR_FILE
    fi

    echo >&2 "Saving docker image as tar file"
    docker save -o $TAR_FILE naic/benchmark-$suffix-$ARCH:latest


    if [ -e $SIF_FILE ]; then
        rm $SIF_FILE
    fi
    singularity build $SIF_FILE docker-archive://$TAR_FILE

    echo >&2 "Cleaning up $TAR_FILE"
    rm $TAR_FILE 
}

while getopts "hg:ds" option; do
    case $option in
        g)
            GPU_FRAMEWORK=$OPTARG
            ;;
        d)
            BUILD_DOCKER=1
            ;;
        s)
            BUILD_SINGULARITY=1
            ;;
        h)
            echo "usage $0"
            echo "options:"
            echo "    -d   build docker image"
            echo "    -s   build singularity image from existing docker image"
            ;;
        *)
            ;;
    esac
done

if [ -n "$BUILD_DOCKER" ]; then
    build_docker $GPU_FRAMEWORK
fi

if [ -n "$BUILD_SINGULARITY" ]; then
    build_singularity_image $GPU_FRAMEWORK

    echo "Run the following to start:"
    echo "    singularity shell -B $(realpath -L $PWD/../../data/lambdal):/data --nv naic-benchmark.$GPU_FRAMEWORK-$ARCH.sif"
fi

