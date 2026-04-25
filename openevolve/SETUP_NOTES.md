# OpenEvolve setup notes (4cycle project)

## Environment

OpenEvolve runs in its **own** micromamba env, separate from the `4cycle` env.
Mixing them causes dep drift (openevolve pulls `openai`, `anthropic`, `flask`,
`dacite`; 4cycle pulls pysat / cp-sat / igraph / etc.).

```bash
micromamba create -n openevolve python=3.11 -y
micromamba activate openevolve
cd /mnt/c/Users/adity/Downloads/4cycle/openevolve
pip install -e ".[dev]"
```

Activate `openevolve` only when running evolution. Keep `4cycle` for graph_db
and α-solver work.

## Calling 4cycle code from an openevolve evaluator

Two options:

1. `pip install -e /mnt/c/Users/adity/Downloads/4cycle` into the openevolve env.
2. Shell out from the evaluator:
   `subprocess.run(["micromamba", "run", "-n", "4cycle", "python", ...])`.

Option 2 is cleaner — envs stay isolated, 4cycle's native deps don't leak in.

## LLM backends wired in

| Backend    | Config                              | Notes                                   |
|------------|-------------------------------------|-----------------------------------------|
| Anthropic  | `configs/claude.yaml`               | Needs `ANTHROPIC_API_KEY` (Console, not Enterprise plan) |
| Ollama     | `configs/local_ollama.yaml`         | Laptop, 8 GB VRAM, Qwen2.5-Coder-7B Q4  |
| vLLM+OptiLLM | `configs/local_vllm_optillm.yaml` | A40 server, Qwen2.5-Coder-32B AWQ + MoA |

Model names starting with `claude-` auto-route to `AnthropicLLM`; everything
else goes through `OpenAILLM` (which is OpenAI-compatible and works with
Ollama / vLLM / OptiLLM endpoints unchanged).

## WSL GPU sanity check

Before pulling models, confirm `nvidia-smi` works inside WSL. If it doesn't,
update the Windows NVIDIA driver — that's what exposes the GPU to WSL2. No
separate Linux driver required.
