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
N_MIN=20
N_MAX=30

micromamba activate "$ENV"
cd "$REPO"
mkdir -p logs/pipeline logs/search logs/cores

# Try to enable native core dumps; HTCondor may pin the hard limit at 0, in
# which case we fall through silently and rely on Python's faulthandler (which
# run_proof_pipeline.py registers for SIGILL/SEGV/ABRT/BUS/FPE) for the trace.
ulimit -c unlimited 2>/dev/null || echo "[run_job] could not raise core limit (hard-capped by condor_starter); faulthandler will still catch traps"
export PYTHONFAULTHANDLER=1

# Phase-1 (easy scan)  : 4 α-tracks × 4 threads = 16 CPUs
# Phase-3 (hard boxes) : skipped — the N≥21 boundary boxes are not closing with
#                        available timeouts (see logs/optimality_proofs.json).
#                        Run targeted prove_box jobs separately once we have
#                        better params; this pipeline just collects easy-scan
#                        c* witnesses so N=22..30 progress isn't blocked by one
#                        stuck 7h box.
python scripts/run_proof_pipeline.py \
    --n-min "$N_MIN" --n-max "$N_MAX" \
    --easy-timeout 300 --easy-workers 4 --alpha-tracks 4 \
    --skip-hard \
    --save-graphs
