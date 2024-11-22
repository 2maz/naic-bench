#!/usr/bin/bash

python /NAIC/software/pytorch-benchmark/inference-benchmark.py --label $NAME_GPU -o /results/inference-benchmark-$NAME_GPU.json $@
