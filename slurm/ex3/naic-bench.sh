#!/bin/bash
SCRIPT_DIR=$(realpath -L $(dirname $0))

NODENAME=$1
GPU_COUNT=${2:-1}

PARTITION=$(scontrol show node $NODENAME | grep Partitions= | sed 's#.*Partitions=##' | cut -d',' -f1)

echo "NODENAME=$NODENAME"
echo "PARTITION=$PARTITION"
echo "ACCOUNT=$USER"
echo "GPU_COUNT=$GPU_COUNT"

cd $SCRIPT_DIR
if [ ! -d generated ]; then
    mkdir generated
fi
cp naic-bench.template.sh generated/naic-bench-$NODENAME.sh

sed -i "s#NODENAME#$NODENAME#g" generated/naic-bench-$NODENAME.sh
sed -i "s#PARTITION#$PARTITION#g" generated/naic-bench-$NODENAME.sh
sed -i "s#ACCOUNT#$USER#g" generated/naic-bench-$NODENAME.sh
# ensure via range 0,/regex/ that only the first entry is replaced
sed -i "0,/GPU_COUNT/s#GPU_COUNT#$GPU_COUNT#" generated/naic-bench-$NODENAME.sh

echo "Generated SLURM Script: generated/naic-bench-$NODENAME.sh"

