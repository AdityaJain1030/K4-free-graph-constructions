#!/bin/bash
# Cluster launcher — cluster_sat box scan, find-mode, N=22..40.
#
# Mirror of cluster_sat/run_cluster_sat.sh. Both invoke the same
# driver (cluster_sat/sat_exact.py); pick whichever submission
# directory fits your local convention (cluster/ vs cluster_sat/).
#
# Edit:
#   - REPO : path to the checked-out 4cycle repo on the cluster
#   - ENV  : micromamba env with ortools + networkx + nauty

set -euo pipefail

eval "$(micromamba shell hook -s bash)"

REPO="/home/adityaj8/k4free"
ENV="k4free"

micromamba activate "$ENV"
cd "$REPO"

mkdir -p logs/sat_box

export PYTHONFAULTHANDLER=1
ulimit -c unlimited 2>/dev/null || true

STAMP=$(date +%Y%m%d_%H%M%S)
PROGRESS="logs/sat_box/progress_${STAMP}.jsonl"
SUMMARY="logs/sat_box/summary_${STAMP}.json"

# 4 outer × 4 cp = 16 cores. 600s/cell. N=22..40.
# Hajnal cap on rows + c* seed prune + non-SAT seed-hint warm-start.
# Per-row incremental save (graph_db) + JSONL fsync log.
python -u -m cluster_sat.sat_exact \
    --n-min 22 --n-max 40 \
    --workers 4 --cp-workers 4 \
    --time-limit 600 \
    --hajnal \
    --c-seed-from-db \
    --seed-hint \
    --skip-on-timeout \
    -v 2 \
    --save \
    --progress-jsonl "$PROGRESS" \
    --out-json "$SUMMARY"

echo "Run finished at $(date). Progress: $PROGRESS  Summary: $SUMMARY"
