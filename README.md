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

Before running a benchmarks, the necessary input data might have to be downloaded. To trigger this 'prepare' stage of the benchmark,
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

## naic-bench-docker
To facilitate working in a container naic-bench provider a 'wrapper' command - naic-bench-docker.
It will build a predefined docker image from device type specific Dockerfiles in naic-bench/src/naic\_bench/resources/docker/.
The create container will be started in daemon mode and can be reused, restarted (--restart) or completely rebuild (--rebuild).

Calling:
```
naic-bench-docker --data-dir data --device-type nvidia
```
will build the docker image for NVidia, start a container and if not otherwise specified open an interactive docker session.

The container contains a prebuild version of naic-bench, where the above mentioned commands can be executed to prepare and run a benchmark.
Note, that per default the data-dir is mounted as /data in the container and the working directory is naic-workspace.


# License

Copyright (c) 2024-2026 Thomas Roehr, Simula Research Laboratory

This project is licensed under the terms of the [New BSD License](https://opensource.org/license/BSD-3-clause).
You are free to use, modify, and distribute this work, subject to the
conditions specified in the [LICENSE](./LICENSE) file.


# Acknowledgement

This work has been supported by the Norwegian Research Council through
the project [Norwegian Artificial Intelligence Cloud (NAIC)](https://www.naic.no/english/about/) (grant number: 322336).
