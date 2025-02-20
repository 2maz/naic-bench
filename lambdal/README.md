# NAIC Bench(marking)

## Installation

This installation relies on the usage of Nvidia containers. 
So you will have to setup an account to get access the container residing 
at nvcr.io.

To setup the benchmark and download the required datasets:

```
    git clone https://2maz/naic-bench.git
    cd naic-bench/lambdal

    ./prepare.sh
```

Install a prerequisite to get some system infos:
```
    ./prepare-slurm-monitor.sh -d data/ -w .
```


Run the container for the benchmark.
```
    source venv-slurm-monitor/bin/activate
    ./run.sh -i -d data/ -w . -b lambdal
```

When running the container interactively (-i) then:
```
    cd /workspace
    cp -R /scripts/* .

    # list available tasks
    /workspace/benchmarks.d/lamdal.sh -h

    # run task
    /workspace/benchmarks.d/lamdal.sh -d cuda -n 1 -t PyTorch_gnmt_FP16
```
