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
python -m k4free_ilp.run_production --workers 16 24 "$@"
