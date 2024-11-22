#!/usr/bin/bash
set -x
# LAMDAL_BENCHMARK
export NAME_DATASET=all
export NAME_TASKS=all
export TIMEOUT_IN_S=3000


echo "cp -r /scripts/* /workspace; ./run_benchmark.sh ${NAME_TYPE}_${NUM_GPU}x${NAME_GPU}_${NODE} ${NAME_TASKS} $TIMEOUT_IN_S"
cp -r /scripts/* /workspace; ./run_benchmark.sh ${NAME_TYPE}_${NUM_GPU}x${NAME_GPU}_${NODE} ${NAME_TASKS} $TIMEOUT_IN_S



