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

# Run the production sweep with --no-break-on-timeout so the α-loop
# continues past timeouts instead of stopping at the first failure.
# This is critical for n≥26 where higher α values time out but lower
# α values (where the best c_log lives) may still be reachable.
python -m k4free_ilp.run_production \
    --workers "$WORKERS" \
    --timeout "$TIMEOUT" \
    --no-break-on-timeout \
    --max-consecutive-timeouts 5 \
    --lazy-max-cuts 5 \
    -vv \
    $N_VALUES \
    "$@"
