#!/usr/bin/env bash
# Launcher for cluster/VLLM_SERVE.sub — starts a vLLM OpenAI-compatible
# server on the allocated GPUs.
#
# Design:
#   - Qwen2.5-Coder-32B-Instruct bf16: ~64 GB, fits on 2x A40 (96 GB) with
#     ~30 GB spare for KV cache (enough for ~40 parallel 16K-ctx requests).
#   - Tensor parallel = 2 across the two cards.
#   - max-model-len 16384 covers openevolve's prompt (~8-12K) plus output.
#   - Port 8000 is the default; change here AND in the openevolve config
#     / SSH tunnel if 8000 is contested on your nodes.
#
# Edit:
#   REPO  : path to the checked-out 4cycle repo on the server (mirrors
#           run_job.sh)
#   ENV   : micromamba env with vllm + torch + cuda
#   MODEL : any HF model id that fits in 2x48 GB; e.g. for a smaller
#           footprint swap in Qwen/Qwen2.5-Coder-14B-Instruct.

set -euo pipefail

eval "$(micromamba shell hook -s bash)"

REPO="/home/adityaj8/k4free"
ENV="vllm"
MODEL="Qwen/Qwen2.5-Coder-32B-Instruct"
PORT="${VLLM_PORT:-8000}"

# Keep the HF cache on shared scratch so re-runs don't re-download the
# 65 GB of weights. Unset / override if your cluster lays out scratch
# differently.
export HF_HOME="${HF_HOME:-/scratch/$USER/hf}"
mkdir -p "$HF_HOME"

micromamba activate "$ENV"
cd "$REPO"
mkdir -p logs/vllm

echo "[run_vllm] hostname: $(hostname)"
echo "[run_vllm] gpus:"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
echo "[run_vllm] model: $MODEL"
echo "[run_vllm] port:  $PORT"
echo "[run_vllm] HF_HOME: $HF_HOME"

# exec so the Python server is PID 1 of the job — clean signal handling
# when HTCondor terminates the job, and no orphaned shell between
# condor_rm and the server process.
exec python -m vllm.entrypoints.openai.api_server \
    --model "$MODEL" \
    --tensor-parallel-size 2 \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.92 \
    --host 0.0.0.0 \
    --port "$PORT"
