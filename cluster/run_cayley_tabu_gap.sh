#!/bin/bash
# Cluster launcher for the GAP-backed Cayley tabu sweep.
#
# Driver: scripts/run_cayley_tabu_gap_parallel.py
# Submit: cluster/CAYLEY_TABU_GAP.sub  (32 CPUs, 200 GB)
#
# Edit:
#   - REPO : path to the checked-out 4cycle repo on the server
#   - ENV  : micromamba env with the k4free deps + gap-defaults
#   - sweep knobs below (N range, time per group, iters, restarts)

set -euo pipefail

eval "$(micromamba shell hook -s bash)"

REPO="/home/adityaj8/k4free"
ENV="k4free"

micromamba activate "$ENV"
cd "$REPO"
mkdir -p logs/pipeline logs/search graphs_src/gap_groups

# GAP emits one stderr warning about the `packagemanager` package at
# startup; that's noise, not an error.
export PYTHONFAULTHANDLER=1

# Sweep knobs.
# --workers 32 saturates the 32-core allocation.
# --time-limit 600 gives each SmallGroup a 10-minute tabu budget — the
#   local run established 180s is the floor at N=25; 600s gives comfortable
#   headroom for larger N with more inversion orbits.
# --n-iters / --n-restarts tuned to the knobs that worked locally.
# --better-only skips persisting to graph_db when the new record doesn't
#   improve the existing best c_log for that N under source='cayley_tabu_gap'.
python scripts/run_cayley_tabu_gap_parallel.py \
    --n-lo 10 --n-hi 144 \
    --workers 64 \
    --time-limit 1200 \
    --n-iters 600 --n-restarts 16 \
    --better-only
