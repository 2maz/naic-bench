# This script will prepare the data folder and download all required 
# data elements

export NAME_NGC=pytorch:24.10-py3
export NAME_DATASET=all

function usage() {
    echo "$0 <options>"
    echo "options:"
    echo "-b    benchmark name"
    echo "-d    data directory"
    echo "-h    this help"
    echo "-i    iteractive docker session"
    echo "-w    base/working directory"
}

SCRIPT_DIR=$(realpath -L $(dirname $0))

export BASE_DIR=$PWD
export DATA_DIR=$BASE_DIR/data

while getopts "hib:d:w:" option; do
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
        *)
            ;;
    esac
done

echo "using:"
echo "    SCRIPT_DIR: $SCRIPT_DIR"
echo "    BASE_DIR: $BASE_DIR"
echo "    DATA_DIR: $DATA_DIR"

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

echo "/bin/bash -c \"cp -r /scripts/* /workspace;  ./run_prepare.sh $NAME_DATASET\""

DL_EXAMPLES_DIR_FULLPATH=$(realpath -L $DL_EXAMPLES_DIR)
DL_BENCHMARK_DIR_FULLPATH=$(realpath -L $DL_BENCHMARK_DIR)

docker run \
    --user 0:$(id -g) \
    -it \
    --rm --shm-size=16g \
    --gpus device=$CUDA_VISIBLE_DEVICES \
    -v ${DL_EXAMPLES_DIR_FULLPATH}/PyTorch:/workspace/benchmark \
    -v ${DATA_DIR}:/data \
    -v ${DL_BENCHMARK_DIR_FULLPATH}/pytorch/scripts:/scripts \
    nvcr.io/nvidia/${NAME_NGC} \
    /bin/bash -c "cp -r /scripts/* /workspace;  ./run_prepare.sh $NAME_DATASET"
