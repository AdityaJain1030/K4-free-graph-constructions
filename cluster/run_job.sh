#!/bin/bash
# Cluster-job template — N=34 SAT-exact push seeded with 2·P(17).
#
# Goal: prove (or disprove) that 2·P(17) is the c-optimal K4-free graph on
# 34 vertices, i.e. that no non-Cayley graph on 34 vertices beats
# c = 24/(17·ln 8) ≈ 0.6789. Cayley case is already exhaustively closed
# (Z_34 and D_17; verify_p17_lift.py, verify_dihedral.py).
#
# The driver scripts/run_n34_push.py:
#   • seeds SATExact with 2·P(17) directly (CirculantSearchFast is
#     heuristic and not guaranteed to find this graph),
#   • runs the Pareto scan with c_log_prune to kill every box whose
#     c-bound ≥ 0.6789,
#   • hard-box-proves the remaining (α ≤ 5 boxes with d ≤ cutoff and
#     any α=6 box with d<8 that survives the scan).
#
# Edit:
#   - REPO : path to the checked-out 4cycle repo on the server
#   - ENV  : micromamba env with ortools + networkx + numpy
#   - timeouts/workers : match PROOF_PIPELINE.sub's request_cpus and RAM

set -euo pipefail

eval "$(micromamba shell hook -s bash)"

REPO="/home/adityaj8/k4free"
ENV="k4free"

micromamba activate "$ENV"
cd "$REPO"
mkdir -p logs/pipeline logs/search logs/cores

# HTCondor often pins the hard core-file limit at 0; faulthandler in the
# Python driver will still capture SIGILL/SEGV/ABRT/BUS/FPE.
ulimit -c unlimited 2>/dev/null || echo "[run_job] core limit capped; using faulthandler"
export PYTHONFAULTHANDLER=1

# Phase-1 (easy scan)  : 8 α-tracks × 4 threads = 32 CPUs
# Phase-3 (hard boxes) : 32 threads on one box at a time, 2h initial
#                        timeout, escalating to 12h ceiling.
python scripts/run_n34_push.py \
    --easy-timeout 600 --easy-workers 4 --alpha-tracks 8 \
    --hard-timeout 7200 --hard-timeout-max 43200 --hard-workers 32 \
    --seed-hint \
    --save-graphs
