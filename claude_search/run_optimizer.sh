#!/usr/bin/env bash
# Launch the K4-free graph optimizer agent.
#
# Usage:
#   ./run_optimizer.sh           # interactive: you see the session live
#   ./run_optimizer.sh --auto    # non-interactive: one-shot, logs to file
#   ./run_optimizer.sh --auto 30 # non-interactive, asking for 30 iterations
#
# Monitoring (from another terminal):
#   tail -f logs/run_<timestamp>.log   # agent's stdout
#   tail -f results.jsonl              # eval records (one line per candidate)
#   watch -n 10 'micromamba run -n k4free python leaderboard.py | head -20'

# Re-exec under bash if we were invoked with sh/dash
if [ -z "${BASH_VERSION:-}" ]; then
    exec bash "$0" "$@"
fi
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

MODEL="${CLAUDE_MODEL:-claude-sonnet-4-6}"
EFFORT="${CLAUDE_EFFORT:-high}"   # low | medium | high | xhigh
MODE="${1:-interactive}"
ITERATIONS="${2:-20}"

# Validate effort level
case "$EFFORT" in
    low|medium|high|xhigh) ;;
    *) echo "ERROR: CLAUDE_EFFORT=$EFFORT not one of: low, medium, high, xhigh" >&2; exit 2 ;;
esac

mkdir -p logs
TS="$(date +%Y%m%d_%H%M%S)"
LOG="logs/run_${TS}.log"

# Make sure the k4free env is available as just "python" so CLAUDE.md's
# sample commands work. Prefer activation; fall back to shim via PATH.
if command -v micromamba >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    eval "$(micromamba shell hook --shell bash)"
    micromamba activate k4free
else
    echo "WARNING: micromamba not on PATH; assuming 'python' already resolves to the k4free env" >&2
fi

# Write the effort level into settings.local.json so Claude Code picks it up.
python - <<PY
import json, pathlib
p = pathlib.Path(".claude/settings.local.json")
d = json.loads(p.read_text())
d["effortLevel"] = "$EFFORT"
p.write_text(json.dumps(d, indent=2) + "\n")
print(f"effortLevel set to: $EFFORT")
PY

PROMPT="Read CLAUDE.md and RULES.md first — they are your operating manual and
problem briefing. Follow them exactly.

Mission (one line): find one K4-free graph at one N with
c = α·d_max / (N·ln d_max) < 0.6789. VT / Cayley / SRG have been
historically proved not to achieve this — the target is **non-VT**.
See RULES.md §'Why non-VT is the mission' for the structural reason.

Current state:
  python leaderboard.py     # best per family, recent thoughts section
  python show_best.py       # top 3 with hypothesis/why-non-VT and per-N metrics

Loop per CLAUDE.md:
  1. Read tail of thoughts.md and all of insights.md.
  2. Read leaderboard.py / show_best.py output.
  3. Pick a non-VT direction (see CLAUDE.md §iteration-loop menu).
  4. Write candidates/gen_NNN_*.py with the required header block
     (Family / Parent / Hypothesis / Why non-VT — RULES.md §file format).
  5. python eval.py candidates/gen_NNN_*.py --quick  (or without --quick for full).
  6. Append to insights.md (1-3 lines on structural observation) and
     thoughts.md (one paragraph on process).
  7. Go to 1.

Rules of engagement (RULES.md is authoritative):
- Focus on constructions, not on N. Let the pipeline evaluate every N;
  returning [] where your idea doesn't apply is correct.
- A single (N, G) pair with c < 0.6789 is a complete win at any N.
- Scoring is pure minimization: score = best_c + 0.001·code_length.
  Breadth across N is NOT rewarded.
- Iteration horizon is long: 150+ candidates across 8+ structurally
  distinct non-VT families. Checkpoint every 25 in thoughts.md; do not
  stop early.

Never touch eval.py, graph_utils.py, leaderboard.py, show_best.py,
RULES.md, CLAUDE.md, or results.jsonl. Never install packages.

Stop only when one of:
  (a) you find c < 0.6789 (the goal — submit and stop),
  (b) 150+ candidates across 8+ families with no remaining angle, or
  (c) the human intervenes."

case "$MODE" in
    interactive|-i)
        echo "Launching interactive Claude Code with model=$MODEL"
        echo "(Terminal output is what you see; no automatic log file in interactive mode.)"
        echo
        claude --model "$MODEL" --permission-mode acceptEdits \
               --strict-mcp-config "$PROMPT"
        ;;
    --auto|auto|-a)
        echo "Launching one-shot (autonomous) run with model=$MODEL"
        echo "Log: $LOG"
        echo "Tail it with:  tail -f $LOG"
        echo
        claude --model "$MODEL" --permission-mode acceptEdits \
               --strict-mcp-config --output-format stream-json --verbose \
               -p "$PROMPT" 2>&1 \
            | python -u scripts/stream_pretty.py \
            | tee "$LOG"
        echo
        echo "Run complete. Final leaderboard:"
        python leaderboard.py | head -15
        ;;
    *)
        echo "Unknown mode: $MODE"
        echo "Usage: $0 [--auto [iterations]]"
        exit 2
        ;;
esac
