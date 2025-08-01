#!/usr/bin/bash

# LAMDAL_BENCHMARK
export GPU_COUNT=${GPU_COUNT:-1}
NODE=${NODE:-$HOSTNAME}

export NAME_TYPE=${NAME_TYPE:-"test"}

APT_INSTALL_PKGS=""
if [ -z "$(command -v bc)" ]; then
    APT_INSTALL_PKGS="bc"
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PYTHON_VENV_INSTALLED=$(dpkg-query -W --showformat='${Status}' python$PYTHON_VERSION-venv | grep 'install ok installed')
if [ -z "$PYTHON_VENV_INSTALLED" ]; then
    APT_INSTALL_PKGS="${APT_INSTALL_PKGS} python$PYTHON_VERSION-venv"
fi

if [ "$APT_INSTALL_PKGS" != "" ]; then
    apt update && apt install -y $APT_INSTALL_PKGS
fi

if ! command -v slurm-monitor > /dev/null; then
    echo "Installing slurm-monitor"
    pip install "slurm-monitor[restapi] @ git+https://github.com/2maz/slurm-monitor"
fi

export GPU_NAME=`echo "$(slurm-monitor system-info -q gpus.model)" | tr ' ' '-' | tr '/[]()' '-' | sed 's/-$//g' | sed 's/--/-/g'`
export GPU_SIZE=`echo $(slurm-monitor system-info -q gpus.memory_total)/1024^3 | bc`
export GPU_COUNT=`echo $(slurm-monitor system-info -q gpus.count)`
export GPU_FRAMEWORK=`slurm-monitor system-info -q gpus.framework`

export NAME_DATASET=all
export NAME_TASKS=all
export TIMEOUT_IN_S=6000
export WORKSPACE_DIR=$PWD
export GPU_DEVICE_TYPE=cuda

export PREPARE_BENCHMARK_ONLY=0
export RUN_BENCHMARK_ONLY=0

HELP_REQUIRED=0

while getopts "hd:t:prw:n:o:l:" option; do
    case $option in
    h)
        HELP_REQUIRED=1
        break;;
    d)
        export GPU_DEVICE_TYPE=$OPTARG
        ;;
    l)
        # setting label
        export NAME_TYPE=$OPTARG
        ;;
    n)
        DESIRED_GPU_COUNT=$OPTARG
        if [ $DESIRED_GPU_COUNT -gt $GPU_COUNT ]; then
            echo "You requested more than the available number of GPUs: $DESIRED_GPU_COUNT ($GPU_COUNT available)"
            exit 30
        fi
        export GPU_COUNT=$DESIRED_GPU_COUNT
        ;;	
    o)
        export RESULTS_DIR=$OPTARG
        ;;
    p)  
        export PREPARE_BENCHMARK_ONLY=1
        ;;
    r)
        export RUN_BENCHMARK_ONLY=1
        ;;
    t)
        export NAME_TASKS=$OPTARG
        ;;
    w)
        export WORKSPACE_DIR=$OPTARG
        ;;
    *)
        ;;
    esac
done

echo "$0 ${NAME_TYPE}_${GPU_COUNT}x${GPU_NAME}_${NODE} ${NAME_TASKS} $TIMEOUT_IN_S"

if [ ! -e $WORKSPACE_DIR/tasks.sh ]; then
    if [ -e /scripts/tasks.sh ]; then
        echo "Preparing current directory by copying scripts from /scripts/"
        cp -R /scripts/* .
    fi

    if [ ! -e $WORKSPACE_DIR/tasks.sh ]; then
    	echo "Missing declaration of tasks in $WORKSPACE_DIR"
    	exit 10
    fi
fi

cd $WORKSPACE_DIR
source $WORKSPACE_DIR/tasks.sh

if [ $HELP_REQUIRED -eq 1 ]; then
    echo "usage: $0 <options>"
    echo "options:"
    echo "  -h                    this help"
    echo "  -l                    label, e.g., cluster name (default: test)"
    echo "  -d <gpu device type>  pick from: cuda,rocm,xpu,hl"
    echo "  -n <number-of-gpus>   number of gpus to use"
    echo "  -o <results-dir>      results directory (/default is /tmp/naic-benchmark-results-dir)"
    echo "  -p                    only prepare benchmark (install required software)"
    echo "  -r                    only run benchmark"
    echo "  -w <workspace dir>    set workspace directory"

    echo "  -t <task-name>        available tasks:"
    for task in "${!TASKS[@]}"; do
    echo "                            $task"
    done
    exit 10
fi

KNOWN_TASK="false"
if [ "$NAME_TASKS" != "all" ]; then
    for task in "${!TASKS[@]}"; do
        if [ "$task" == "$NAME_TASKS" ] ; then
        KNOWN_TASK="true"
        fi
    done
else
    KNOWN_TASK="true"
fi

if [ "$KNOWN_TASK" == "false" ]; then
    echo "Task: $NAME_TASKS is not known. Use -h to show all available"
    exit 10
fi

torch_version=`python3 -c "import torch; print(torch.__version__)"`
torch_major_minor=`echo $torch_version | sed 's#\([0-9]\.[0-9]\).*+.*#\1#g'`

echo "Run:"
echo "    task:   $NAME_TASKS (use -h to show all available)"
echo "    device: $GPU_DEVICE_TYPE"
echo "    pytorch: $torch_version"


case $GPU_DEVICE_TYPE in
    xpu)
    if (( $(echo "$torch_major_minor 2.5" | awk '{print ($1 < $2)}') )); then
        echo "uv pip install --system torch torchvision torchaudio --index-url https://download.pytorch.org/whl/test/xpu"
        uv pip install --system torch torchvision torchaudio --index-url https://download.pytorch.org/whl/test/xpu
    fi
    ;;
    *)
        ;;
esac

if [ ! -e "run_benchmark.sh" ]; then
    echo "Missing startup files (run_benchmark.sh) for benchmark. Did you copy/install/mount the deeplearning-benchmark/Python folder"
    exit 10
fi

./run_benchmark.sh ${NAME_TYPE}_${GPU_COUNT}x${GPU_NAME}_${NODE} ${NAME_TASKS} $TIMEOUT_IN_S

