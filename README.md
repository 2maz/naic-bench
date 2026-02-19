# NAIC Bench

A package to run Deep Learning Examples for 'simple' benchmarking across
a heterogeneous set of GPUs.

## Installation Requirements

To install this package the following packages/libraries are required:
- git
- g++
- python3-dev (or python3-devel on Fedora-like systems)

### From Source

Install package from source:

```
git clone https://github.com/2maz/naic-bench.git
```

Create a venv and install the package
```
python -m venv venv-naic-bench-$(uname -m)
source venv-naic-bench-$(uname -m)/bin/activate

pip install -e naic-bench
```

## Usage
Using the command line interface:

## naic-bench
Here we describe the basic usage of naic-bench. The main information and description of the benchmarks resides in a conf.d folder.
This package already provides a predefined set of benchmarks.

Before running a benchmark, the necessary input data might have to be downloaded. To trigger this 'prepare' stage of the benchmark,
use 'naic-bench prepare'.

The following example prepares the data required from 'gnmt' benchmark after downloading the source of the benchmark
(specified in the confd's directory under gnmt.yaml) into a subfolder defined by --benchmarks-dir.

```
naic-bench prepare --data-dir data --benchmarks-dir benchmarks --confd-dir resources/naic-bench/src/naic_bench/resources/conf.d --benchmark gnmt
```

Once the data has been downloaded, the benchmark can be executed.

```
naic-bench run --data-dir data/ --benchmarks-dir benchmarks --confd-dir naic-bench/src/naic_bench/resources/conf.d --benchmark gnmt --variant fp16 --device-type cuda --gpu-count 1
```

### Benchmark Specification

Each benchmark is specified using a yaml file - examples can be found in the [resources/conf.d](https://github.com/2maz/naic-bench/tree/main/src/naic_bench/resources/conf.d) folder, associated with this library.

The configurations allow the use of placeholders:

Placeholder | Description
:---------  |:------------
GPU_COUNT   | Number of GPUs to be used (specified via --gpu-count)
CPU_COUNT   | Number of CPUs to be used (defaults to os.cpu\_count())
TMP_DIR     | The main temp directory (specified via --output-base-dir)
DATA_DIR    | The data directory (specified via --data-dir)

The basic outline is:
```
pytorch: # name-of-testing-framework
  my-benchmark: # name of the benchmark
    repo:
      url: https://github.com/your-repo/your-benchmark.git # a repository hosting the benchmark
    command: >
      python run.py
    command_distributed: >
      torch -m torch.distributed.run --nproc_per_node={{GPU_COUNT}} run.py
    prepare:
      data: my-benchmark.prepare
    metrics:
      throughput:
          pattern: "This benchmarks throughput\\s*:\\s*([0-9\\.+e])"
    variants:
       fp32:
          base_dir: subfolder_in_repo/my_benchmark/
          batch_size:
            size_1gb:
              default: 1
              overrides:
                xpu: 0.5
            multiple_gpu_scaling:
              default: 0.9
              overrides:
                xpu: 0.8.5
            apply_via: --training-batch-size
          arguments:
             mode: training
             data: "{{DATA_DIR}}/data-for-my-benchmark
             save: "{{TMP_DIR}}/models"
```

#### Using prepare scirpt
Running a 'prepare' script, e.g., my-benchmark.prepare will be done with the shell environment variable set:

Environment Variable | Description
:-----------         |:------------
BENCHMARK_DIR       | Number of GPUs to be used (specified via --gpu-count)
DATA_DIR            | The data directory (specified via --data-dir)

So you can write:

```
#!/bin/bash
set -e
echo "Downloading data required for my-benchmark

pushd .
mkdir -p $DATA_DIR/data-for-my-benchmark

# the specific download script that comes with the benchmark project
$BENCHMARK_DIR/data-download.sh $DATA_DIR/squad
```


## naic-bench docker
To facilitate working in a container naic-bench provider a 'wrapper' command - naic-bench-docker.
It will build a predefined docker image from device type specific Dockerfiles in naic-bench/src/naic\_bench/resources/docker/.
The create container will be started in daemon mode and can be reused, restarted (--restart) or completely rebuild (--rebuild).

Calling:
```
naic-bench docker --data-dir data --device-type nvidia
```
will build the docker image for NVidia, start a container and if not otherwise specified open an interactive docker session.

The container contains a prebuild version of naic-bench, where the above mentioned commands can be executed to prepare and run a benchmark.
Note, that per default the data-dir is mounted as /data in the container and the working directory is naic-workspace.

## naic-bench singularity
Since docker might not be permitted to run on a system that should be benchmark, singularity is an option.
The current approach is to build a docker image and create a singularity image from that.
Hence, one might need to you a separate system to build the docker image and derive the singularity image from it.
The general process is:
a. create docker image
b. save docker image as tar
c. create singularity image, creating it from the tar file

Calling the following with do all the previously mentioned steps behind the scenes, if necessary.
If a container is already running, it will be reused.

```
naic-bench singularity --data-dir data --device-type nvidia
```

If the container that is currently in use, needs to be restarted -- call with --restart

```
naic-bench singularity --data-dir data --device-type nvidia --restart
```

When the --device-type argument is omitted, the GPU (as device-type) will be autodetected, i.e.,
typically the device type is only necessary when building an image for another kind of system.


# License

Copyright (c) 2024-2026 Thomas Roehr, Simula Research Laboratory

This project is licensed under the terms of the [New BSD License](https://opensource.org/license/BSD-3-clause).
You are free to use, modify, and distribute this work, subject to the
conditions specified in the [LICENSE](./LICENSE) file.


# Acknowledgement

This work has been supported by the Norwegian Research Council through
the project [Norwegian Artificial Intelligence Cloud (NAIC)](https://www.naic.no/english/about/) (grant number: 322336).
