#!/usr/bin/env bash
# Usage:
#   bash examples/k4free_min_c_alpha/run_gemini.sh [ALPHA_MAX] [ITERATIONS]
#
# Defaults: ALPHA_MAX=4, ITERATIONS=30.
#
# Requires:
#   export GEMINI_API_KEY=...           # https://aistudio.google.com/apikey

set -eu

ALPHA="${1:-4}"
ITERS="${2:-30}"

if [ -z "${GEMINI_API_KEY:-}" ]; then
    echo "error: GEMINI_API_KEY is not set" >&2
    exit 1
fi

cd "$(dirname "$0")/../.."

OUT="examples/k4free_min_c_alpha/out_alpha${ALPHA}_gemini"
mkdir -p "$OUT"

echo "=== k4free_min_c_alpha ALPHA_MAX=${ALPHA} iters=${ITERS} (gemini flash-lite) ==="
echo "output dir: $OUT"

K4FREE_ALPHA="$ALPHA" micromamba run -n openevolve python openevolve-run.py \
    examples/k4free_min_c_alpha/initial_program.py \
    examples/k4free_min_c_alpha/evaluator.py \
    --config examples/k4free_min_c_alpha/config_gemini.yaml \
    --iterations "$ITERS" \
    --output "$OUT" \
    2>&1 | tee "$OUT/run.log"

echo "=== done — best program: $OUT/best/best_program.py ==="
