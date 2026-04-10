#!/bin/bash
set -e
echo "Starting regular_sat sweep at $(date)"
echo "Host: $(hostname), CPUs: $(nproc), RAM: $(free -g | awk '/Mem:/{print $2}')GB"

# IMPORTANT: --workers must match request_cpus in REGULAR_SAT.sub
# os.cpu_count() sees ALL machine CPUs, not the HTCondor allocation
WORKERS=16

# Full scan over known ranges
python -m regular_sat.cli scan --n_min 12 --n_max 35 --time_limit 3600 --workers $WORKERS

# Individual hard cases with longer limits
python -m regular_sat.cli single --n 24 --time_limit 7200 --workers $WORKERS
python -m regular_sat.cli single --n 33 --time_limit 7200 --workers $WORKERS
python -m regular_sat.cli single --n 35 --time_limit 7200 --workers $WORKERS

echo "Finished at $(date)"
