export NAME_NGC=pytorch:24.10-py3
export NAME_DATASET=all

export LAMBDAL_DATA_DIR=/global/D1/projects/NAIC/data/lambdal/
export LAMBDAL_BASE_DIR=/global/D1/projects/NAIC/software/lambdal/

export DL_BENCHMARK_DIR=$LAMBDAL_BASE_DIR/deeplearning-benchmark/pytorch
export DL_EXAMPLES_DIR=$LAMBDAL_BASE_DIR/DeepLearningExamples

SCRIPT_DIR=$(realpath -L $(dirname $0))
export RESULTS_DIR=$SCRIPT_DIR/results/${NAME_RESULTS}

docker login nvcr.io
docker pull nvcr.io/nvidia/${NAME_NGC}

SCRIPT_DIR=$(realpath -L $(dirname $0))

# Clone repos
git clone https://github.com/2maz/DeepLearningExamples.git && \
    cd DeepLearningExamples && \
    git checkout lambda/benchmark && \
    git pull origin lambda/benchmark && \
    cd ..

git clone https://github.com/2maz/deeplearning-benchmark.git && \
cd deeplearning-benchmark/pytorch

# Prepare data
mkdir $LAMBDAL_DATA_DIR

docker run \
    --gpus device=$CUDA_VISIBLE_DEVICES \
    --rm --shm-size=256g \
    -v ${DL_EXAMPLES_DIR}/PyTorch:/workspace/benchmark \
    -v ${LAMBDAL_DATA_DIR}:/data \
    -v ${DL_BENCHMARK_DIR}/scripts:/scripts \
    nvcr.io/nvidia/${NAME_NGC} \
    /bin/bash -c "cp -r /scripts/* /workspace;  ./run_prepare.sh $NAME_DATASET"
