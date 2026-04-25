#!/usr/bin/env bash
# Usage:
#   bash examples/k4free_min_c/run_cluster.sh [N] [ITERATIONS]
#
# Assumes a vLLM OpenAI-compat endpoint reachable at $VLLM_BASE_URL.
# Defaults to http://localhost:8000/v1 (local node, or SSH-tunneled).
#
# Example (cluster head node, after tunneling gpu-node42:8000 -> :8000):
#   bash examples/k4free_min_c/run_cluster.sh 14 50
#
# Example (explicit remote host):
#   VLLM_BASE_URL=http://gpu-node42.cluster:8000/v1 \
#     bash examples/k4free_min_c/run_cluster.sh 15

set -eu

N="${1:-14}"
ITERS="${2:-30}"
export VLLM_BASE_URL="${VLLM_BASE_URL:-http://localhost:8000/v1}"

# Quick health check — fail fast if vLLM isn't serving.
if ! curl -sf -o /dev/null "${VLLM_BASE_URL%/v1}/v1/models"; then
    echo "error: vLLM endpoint at $VLLM_BASE_URL is not responding" >&2
    echo "  - did vLLM finish loading weights? tail the cluster log" >&2
    echo "  - is the SSH tunnel up? ssh -L 8000:<gpu-node>:8000 ..." >&2
    exit 1
fi

cd "$(dirname "$0")/../.."

OUT="examples/k4free_min_c/out_n${N}_cluster"
mkdir -p "$OUT"

echo "=== k4free_min_c N=${N} iters=${ITERS} (vLLM @ $VLLM_BASE_URL) ==="

K4FREE_N="$N" micromamba run -n openevolve python openevolve-run.py \
    examples/k4free_min_c/initial_program.py \
    examples/k4free_min_c/evaluator.py \
    --config examples/k4free_min_c/config_cluster.yaml \
    --iterations "$ITERS" \
    --output "$OUT" \
    2>&1 | tee "$OUT/run.log"

echo "=== done — best program: $OUT/best/best_program.py ==="
