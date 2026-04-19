#!/bin/bash
# Cluster-job template for the end-to-end K4-free optimality pipeline.
# Paired with HTCondor submit files in this directory.
#
# Edit:
#   - REPO     : path to the checked-out 4cycle repo on the server
#   - ENV      : micromamba env with ortools + networkx + numpy
#   - N_MIN / N_MAX : range of N to prove
#   - resource kwargs : match the .sub file's request_cpus and RAM

set -euo pipefail

eval "$(micromamba shell hook -s bash)"

REPO="/home/adityaj8/k4free"
ENV="k4free"
N_MIN=30
N_MAX=40

micromamba activate "$ENV"
cd "$REPO"
mkdir -p logs/pipeline logs/search

# Phase-1 (easy scan)  : 8 α-tracks × 4 threads = 32 CPUs
# Phase-3 (hard boxes) : one CP-SAT per box, 32 threads
python scripts/run_proof_pipeline.py \
    --n-min "$N_MIN" --n-max "$N_MAX" \
    --easy-timeout 300 --easy-workers 4 --alpha-tracks 8 \
    --hard-timeout 3600 --hard-timeout-max 14400 --hard-workers 32 \
    --save-graphs
