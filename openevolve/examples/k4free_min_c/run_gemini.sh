#!/usr/bin/env bash
# Usage:
#   bash examples/k4free_min_c/run_gemini.sh [N] [ITERATIONS]
#
# Defaults: N=14, ITERATIONS=30.
#
# Requires:
#   export GEMINI_API_KEY=...            # https://aistudio.google.com/apikey
#   openevolve micromamba env (already installed at ~/micromamba/envs/openevolve)

set -eu

N="${1:-14}"
ITERS="${2:-30}"

if [[ -z "${GEMINI_API_KEY:-}" ]]; then
    echo "error: GEMINI_API_KEY is not set" >&2
    echo "get a key at https://aistudio.google.com/apikey, then: export GEMINI_API_KEY=..." >&2
    exit 1
fi

# Run from the openevolve repo root so relative example paths resolve.
cd "$(dirname "$0")/../.."

OUT="examples/k4free_min_c/out_n${N}_gemini"
mkdir -p "$OUT"

echo "=== k4free_min_c N=${N} iters=${ITERS} (gemini) ==="
echo "output dir: $OUT"

K4FREE_N="$N" micromamba run -n openevolve python openevolve-run.py \
    examples/k4free_min_c/initial_program.py \
    examples/k4free_min_c/evaluator.py \
    --config examples/k4free_min_c/config_gemini.yaml \
    --iterations "$ITERS" \
    --output "$OUT" \
    2>&1 | tee "$OUT/run.log"

echo "=== done — best program: $OUT/best/best_program.py ==="
