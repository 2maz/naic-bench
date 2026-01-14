# This script will prepare the data folder and download all required
# data elements

export NAME_NGC=pytorch:24.10-py3
export NAME_DATASET=all

function usage() {
    echo "$0 <options>"
    echo "options:"
    echo "-d    data directory"
    echo "-h    this help"
    echo "-w    base/working directory"
    echo "-n    name of the dataset"
}

SCRIPT_DIR=$(realpath -L $(dirname $0))

export BASE_DIR=$PWD
export DATA_DIR=$BASE_DIR/data

while getopts "hd:w:n:" option; do
    case $option in
        d)
            DATA_DIR=$(realpath -L $OPTARG)
            export DATA_DIR
            ;;
        h)
            usage
            exit 0
            ;;
        w)
            BASE_DIR=$(realpath -L $OPTARG)
            export BASE_DIR
            ;;
        n)
            NAME_DATASET=$OPTARG
            ;;
        *)
            ;;
    esac
done

echo "using:"
echo "    SCRIPT_DIR: $SCRIPT_DIR"
echo "    BASE_DIR: $BASE_DIR"
echo "    DATA_DIR: $DATA_DIR"
echo "    NAME_DATASET: $NAME_DATASET"

SCRIPT_DIR=$(realpath -L $(dirname $0))
export RESULTS_DIR=$SCRIPT_DIR/results/${NAME_RESULTS}

if ! command -v docker; then
    echo "'docker' command is not available. Install docker, or load module"
    exit 10
fi

# Clone repos
DL_EXAMPLES_DIR=naic-DeepLearningExamples
if [ ! -d $DL_EXAMPLES_DIR ]; then
    git clone -b lambda/benchmark https://github.com/2maz/$DL_EXAMPLES_DIR.git && \
        cd $DL_EXAMPLES_DIR && \
        cd ..
else
    echo "$DL_EXAMPLES_DIR already exists. Please update manually if necessary (via git pull)"
fi


DL_BENCHMARK_DIR=naic-deeplearning-benchmark
if [ ! -d $DL_BENCHMARK_DIR ]; then
    git clone -b dev https://github.com/2maz/$DL_BENCHMARK_DIR.git && \
        cd $DL_BENCHMARK_DIR/pytorch
else
    echo "$DL_BENCHMARK_DIR already exists. Please update manually if necessary (via git pull)"
fi

DL_BENCHMARKS_D_DIR=benchmarks.d
if [ ! -d $DL_BENCHMARKS_D_DIR ]; then
    ln -s $SCRIPT_DIR/$DL_BENCHMARKS_D_DIR $DL_BENCHMARKS_D_DIR
fi

echo "Trying to connect to nvidia container hub: nvcr.io"
docker login nvcr.io
docker pull nvcr.io/nvidia/${NAME_NGC}

# Prepare data
if [ ! -d $DATA_DIR ]; then
    mkdir $DATA_DIR
else
    while [ 0 ]; do
        echo "Data directory: $DATA_DIR already exists. Continue? [Y|n]"
        read answer

        if [[ "$answer" =~ ^[yY] ]]; then
            break
        elif [[ "$answer" =~ ^[nN] ]]; then
            exit 20
        fi
    done
fi

echo "/bin/bash -c \"cp -r /scripts/* /workspace;  cd workspace; ./run_prepare.sh $NAME_DATASET /data /workspace/benchmark\" "

DL_EXAMPLES_DIR_FULLPATH=$(realpath -L $DL_EXAMPLES_DIR)
DL_BENCHMARK_DIR_FULLPATH=$(realpath -L $DL_BENCHMARK_DIR)

docker run \
    -t \
    --rm \
    --gpus device=$CUDA_VISIBLE_DEVICES \
    nvcr.io/nvidia/${NAME_NGC} \
    /bin/bash -c "echo \"SUCCESS\""

if [ $? -ne 0 ]; then
    echo ""
    echo "WARNING"
    echo "Failed to used nvidia docker image - falling back to ubuntu:24.04"
    echo "Note that ncf dataset will not be downloaded [PRESS ENTER TO CONTINUE]"
    echo ""
    read answer

    # UBUNTU IMAGE USED - works for most datasets
    docker run \
        --user 0:$(id -g) \
        -it \
        --rm --shm-size=16g \
        -v ${DL_EXAMPLES_DIR_FULLPATH}/PyTorch:/workspace/benchmark \
        -v ${DATA_DIR}:/data \
        -v ${DL_BENCHMARK_DIR_FULLPATH}/pytorch/scripts:/scripts \
        ubuntu:22.04 \
        /bin/bash -c "cp -r /scripts/* /workspace;  cd /workspace; ./run_prepare.sh $NAME_DATASET /data /workspace/benchmark"
else
    # NVIDIA DOCKER IMAGE used
    docker run \
        --user 0:$(id -g) \
        -it \
        --rm --shm-size=16g \
        --gpus device=$CUDA_VISIBLE_DEVICES \
        -v ${DL_EXAMPLES_DIR_FULLPATH}/PyTorch:/workspace/benchmark \
        -v ${DATA_DIR}:/data \
        -v ${DL_BENCHMARK_DIR_FULLPATH}/pytorch/scripts:/scripts \
        nvcr.io/nvidia/${NAME_NGC} \
        /bin/bash -c "cp -r /scripts/* /workspace;  cd /workspace; ./run_prepare.sh $NAME_DATASET /data /workspace/benchmark"
fi
