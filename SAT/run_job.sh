#!/bin/bash
set -e

# Setup micromamba environment
eval "$(micromamba shell hook -s bash)"
micromamba activate ILP_pareto_enum

# Run from the project directory
cd /home/adityaj8/k4free/SAT

# Ensure logs directory exists
mkdir -p logs

# Run the production sweep
python -m k4free_ilp.run_production --workers 24 25 26 27 28 29 30 31 32 33 34 35 "$@"
