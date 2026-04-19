#!/bin/bash
set -e

# Setup micromamba environment
eval "$(micromamba shell hook -s bash)"
micromamba activate ILP_pareto_enum

# Run from the project directory
cd /home/adityaj8/k4free/SAT

# Ensure logs directory exists
mkdir -p logs

# --- Configuration ---
WORKERS=16
TIMEOUT=1800
N_VALUES="26 27 28"

# TODO: wire to the current solver. The old `k4free_ilp.run_production`
# CLI was removed; the active entry points are:
#   python scripts/run_sat_exact.py --n $N --workers $WORKERS --timeout $TIMEOUT
#   python scripts/prove_box.py --n $N --alpha $A --d-max $D --workers $WORKERS
# (both from the repo root, not SAT_old/).
echo "run_job.sh is a cluster-job TEMPLATE — edit the command below before use" >&2
exit 1
