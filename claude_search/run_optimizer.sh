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
EFFORT="${CLAUDE_EFFORT:-medium}"   # low | medium | high | xhigh
MODE="${1:-interactive}"
ITERATIONS="${2:-20}"

# Validate effort level
case "$EFFORT" in
    low|medium|high|xhigh) ;;
    *) echo "ERROR: CLAUDE_EFFORT=$EFFORT not one of: low, medium, high, xhigh" >&2; exit 2 ;;
esac

mkdir -p logs
TS="$(date +%Y%m%d_%H%M%S)"
# Write the log on the native Linux filesystem (not /mnt/c drvfs), because
# drvfs defers inode materialization for open-but-unflushed files — the
# log would show as missing via `ls` even while tee holds it open. Symlink
# into logs/ so the documented `tail -f logs/run_<ts>.log` still works.
NATIVE_LOG_DIR="${HOME}/.cache/claude_search_logs"
mkdir -p "$NATIVE_LOG_DIR"
LOG="${NATIVE_LOG_DIR}/run_${TS}.log"
ln -sf "$LOG" "logs/run_${TS}.log"

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

PROMPT="CLAUDE.md is your operating manual (auto-loaded). Follow it exactly.

Mission: find one K4-free graph at one N with
c = α·d_max / (N·ln d_max) < 0.6789. Target is **non-VT** (VT is exhausted).

Your job is **translation, not invention**. NON_VT_CATALOG.md lists ten
named non-VT K4-free constructions with a 'Priority by high-N promise'
table — work them in that priority order, starting with the HIGH-priority
entries. Do not invent new families. Do not start from 'take Paley and
modify it'.

HARD CONSTRAINTS (from CLAUDE.md — the session kills any run that
ignores them):
  - Target N ≥ 34. Eval grid is [30, 100]; small N is not evaluated.
    Your construct MUST produce d_max ≥ 2 at some N ≥ 34 to count.
  - No seed sweeps. Two candidates in the same family must differ
    structurally (new edge rule / base / perturbation), not just by
    random seed. 'Same code, different seed' is banned.
  - At most 2 candidates per catalog entry before moving to the next.
    Port once, optionally perturb once with a specific hypothesis.
  - Mutation requires a specific structural change in the Parent line,
    not 'changed seed' or 'different parameter'.

Iteration loop:
  1. python leaderboard.py   # best per family + recent thoughts
  2. Open NON_VT_CATALOG.md 'Priority by high-N promise' table. Find
     the highest-priority entry that doesn't yet have 2 candidate
     files citing it.
  3. Write candidates/gen_NNN_<entry_tag>.py with
     # Family: <family_tag>
     # Catalog: <entry_tag>
     # Parent: none   (or gen_XXX if mutating)
     # Hypothesis: <one specific sentence; no 'beat Paley' filler>
     # Why non-VT: <one line from the catalog entry>
  4. python eval.py candidates/gen_NNN_*.py --quick
  5. If the eval fails the N ≥ 34 constraint (best_c is only finite
     at small N), rewrite or move on — DO NOT count this toward your
     budget.
  6. If the result told you something structural the catalog didn't
     already predict, append one line to insights.md. Otherwise skip.
  7. Go to 1.

Target: ~200 distinct candidates, each passing the N ≥ 34 d_max
constraint. Checkpoint in thoughts.md at gen_050, gen_100, gen_150.

Never touch eval.py, graph_utils.py, leaderboard.py, show_best.py,
RULES.md, CLAUDE.md, NON_VT_CATALOG.md, or results.jsonl. Never
install packages.

Stop when one of:
  (a) best_c < 0.6789 (the goal — submit and stop),
  (b) 200 valid (N ≥ 34) candidates submitted,
  (c) the human intervenes."

case "$MODE" in
    interactive|-i)
        echo "Launching interactive Claude Code with model=$MODEL"
        echo "Log: $LOG (full TTY session captured via script(1))"
        echo "You can type to nudge Sonnet if it gets stuck thinking."
        echo
        # Export so the subshell script(1) spawns can see them.
        export MODEL PROMPT
        # -q: suppress script(1)'s own start/end banner lines.
        # -f: flush after each write so tail -f works live.
        # -c "...": run the given command in a pty; both output and
        # anything you type go to the log.
        script -q -f \
            -c 'claude --model "$MODEL" --permission-mode acceptEdits --strict-mcp-config "$PROMPT"' \
            "$LOG"
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
