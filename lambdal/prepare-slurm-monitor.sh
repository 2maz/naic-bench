#!/usr/bin/bash

ARCH=$(uname -m)
VENV_NAME=venv-$ARCH-slurm-monitor

if [ ! -d $VENV_NAME ]; then
    echo "Creating venv: $VENV_NAME"
    python3 -m venv $VENV_NAME
    pip install git+https://github.com/2maz/slurm-monitor.git#egg=slurm-monitor[restapi]
else
    echo "Using existing venv: $VENV_NAME"
fi

. venv-$ARCH-slurm-monitor/bin/activate

