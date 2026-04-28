#!/bin/bash
# Cluster launcher — cluster_sat/sat_exact.py box scan, find-mode.
#
# Pipeline: parallel-row K4-free CP-SAT box scan with Hajnal cap,
# c-seed from graph_db, seed-hint warm-start, and per-row incremental
# persistence (graph_db + JSONL).
#
# Edit:
#   - REPO : path to the checked-out 4cycle repo on the cluster
#   - ENV  : micromamba env with ortools + networkx + nauty
#   - --n-min / --n-max, --time-limit, --workers, --cp-workers below
#
# Memory policy
# -------------
# 16 CPUs / 200 GB. The 4 outer workers × 4 cp-workers split caps
# simultaneous models at 4 (one per outer process). At N=40 the
# heaviest surviving cell after Hajnal + c* prune is α≈8 with
# C(40,9)=273M α-clauses — single-cell peak ~30 GB during presolve.
# Four of those in flight ≈ 120 GB peak; the 50 GB buffer absorbs
# the presolve spikes.
#
# Hard cells WILL time out
# ------------------------
# At N=30+ even with seed-hint + Hajnal, some boundary cells (small d
# at frontier α) are too hard to resolve in 600s. They're skipped and
# we move to larger d. That is the explicit goal: find what we can,
# don't burn budget proving UNSAT.

set -euo pipefail

eval "$(micromamba shell hook -s bash)"

REPO="/home/adityaj8/k4free"
ENV="k4free"

micromamba activate "$ENV"
cd "$REPO"

mkdir -p logs/cluster_sat

export PYTHONFAULTHANDLER=1
ulimit -c unlimited 2>/dev/null || true

STAMP=$(date +%Y%m%d_%H%M%S)
PROGRESS="logs/cluster_sat/progress_${STAMP}.jsonl"
SUMMARY="logs/cluster_sat/summary_${STAMP}.json"

# 4 outer × 4 cp = 16 cores. 600s/cell. N=22..40.
# --c-seed-from-db: prune dominated rows pre-dispatch.
# --seed-hint:      bias CP-SAT toward the best non-SAT cached graph.
# --skip-on-timeout: TIMED_OUT cells advance to larger d, never fatal.
# --save:           per-row commit to graph_db (sat_exact source).
# --progress-jsonl: append-and-fsync per row, survives SIGKILL.
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
