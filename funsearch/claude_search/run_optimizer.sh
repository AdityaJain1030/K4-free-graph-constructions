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
#   watch -n 10 'micromamba run -n funsearch python leaderboard.py | head -20'

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

# Make sure funsearch env is available as just "python" so CLAUDE.md's
# sample commands work. Prefer activation; fall back to shim via PATH.
if command -v micromamba >/dev/null 2>&1; then
    # shellcheck disable=SC1091
    eval "$(micromamba shell hook --shell bash)"
    micromamba activate funsearch
else
    echo "WARNING: micromamba not on PATH; assuming 'python' already resolves to the funsearch env" >&2
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

PROMPT="Read RULES.md and CLAUDE.md first (they are your operating manual).

Then run: python leaderboard.py    and    python show_best.py
to see the current state of the search.

Your goal: beat the current best primary score by writing new candidate files
to candidates/gen_NNN_description.py. Focus on algebraic/group-theoretic
constructions (Cayley graphs, circulants, quadratic/cubic residues, strong
products, vertex-blowups). Keep each construct() body under 50 lines.

Iteration loop (repeat up to ${ITERATIONS} times, or until you beat the current best):
  1. Hypothesize an improvement based on what the data shows.
  2. Write candidates/gen_NNN_description.py.
  3. Run: python eval.py candidates/gen_NNN_description.py --quick
  4. If the Stage-1 mean c looks promising (< 1.1), run it again without --quick.
  5. Look at the new leaderboard; decide what to try next.

Never read results.jsonl directly — use leaderboard.py and show_best.py.
Never touch eval.py, graph_utils.py, leaderboard.py, show_best.py, or
results.jsonl. Never install packages.

When you stop, report a short summary: how many candidates you tried, what
the top 3 look like now, and what patterns you observed in the failures."

case "$MODE" in
    interactive|-i)
        echo "Launching interactive Claude Code with model=$MODEL"
        echo "(Terminal output is what you see; no automatic log file in interactive mode.)"
        echo
        claude --model "$MODEL" --permission-mode acceptEdits "$PROMPT"
        ;;
    --auto|auto|-a)
        echo "Launching one-shot (autonomous) run with model=$MODEL"
        echo "Log: $LOG"
        echo "Tail it with:  tail -f $LOG"
        echo
        claude --model "$MODEL" --permission-mode acceptEdits \
               -p "$PROMPT" 2>&1 | tee "$LOG"
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
