#!/bin/bash
set -e

# Setup micromamba environment
eval "$(micromamba shell hook -s bash)"
micromamba activate ILP_pareto_enum

# Run from the project directory
cd /home/adityaj8/k4free/SAT

# Ensure logs directory exists
mkdir -p logs

# Split n=23..35 across two processes (8 workers each = 16 CPUs)
python -m k4free_ilp.run_production 23 25 27 29 31 33 35 --workers 8 -v > logs/odd.log 2>&1 &
PID_ODD=$!
python -m k4free_ilp.run_production 24 26 28 30 32 34    --workers 8 -v > logs/even.log 2>&1 &
PID_EVEN=$!

echo "Started odd n values (PID $PID_ODD) -> logs/odd.log"
echo "Started even n values (PID $PID_EVEN) -> logs/even.log"
echo "Monitoring..."

wait $PID_ODD
echo "Odd batch done (exit $?)"
wait $PID_EVEN
echo "Even batch done (exit $?)"

echo "All done."
