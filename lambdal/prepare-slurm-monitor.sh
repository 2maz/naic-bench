#!/usr/bin/bash

python3 -m venv venv-slurm-monitor
. venv-slurm-monitor/bin/activate

pip install git+https://github.com/2maz/slurm-monitor.git#egg=slurm-monitor[restapi]
