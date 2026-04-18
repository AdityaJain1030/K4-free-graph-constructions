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
to candidates/gen_NNN_description.py. Focus on structurally diverse
algebraic constructions: Cayley graphs on non-cyclic groups (Z/p × Z/q,
dihedral, semidirect products), quadratic/cubic residues in finite fields,
polarity graphs of projective planes, incidence structures of Steiner
systems and block designs, generalized quadrangles, strong/tensor products
of small graphs, vertex-blowups, Mattheus-Verstraete-style pseudorandom
constructions. Keep each construct() body under 50 lines.

**You do NOT need to work at every N.** Stage 1 score is the mean of FINITE
c values only — failures are dropped, not penalized as infinity. A
construction that works at just 2 of the 19 Stage 1 N values but scores
c = 0.5 at those two beats anything averaging 0.8 across all N. The real
goal is finding an infinite FAMILY (e.g., N = q² + q + 1 for prime power q,
or N ∈ {primes ≡ 1 mod 4}) where c stays below 0.6789 asymptotically.
Return []  or raise for N outside your family's sweet spot.

## Don't code-golf

The 0.001 * code_length term in the score is a tiebreaker, not a target.
Saving 20 characters on an already-plateaued circulant does NOT count as
progress — the archive is full of golfed variants of the same graph. Write
clear, readable construct() bodies; invest your effort in finding better
graphs, not shorter code.

## Try weird things sometimes

Every ~3 iterations, throw structure out the window and try something
unusual: a random K4-free graph grown by rejection sampling, a tensor/strong
product of two small graphs, an incidence graph of a Steiner system, a
Kneser-style construction, or edges picked by a hash function you invent.
Invalid or bad results are fine — variety is the point. 

## Work fast, not deeply. If you have a hypothesis, write it and test it. Don't spend more than 30 seconds thinking before writing. Iterate quickly.

- DO NOT try to prove K₄-freeness analytically before writing. eval.py
  validates it for you. Write a plausible construction, eval it, and let
  the tool tell you if it fails. Invalid graphs are cheap signal, not
  wasted effort.
- DO NOT over-reason before picking what to try. Spend a few seconds on
  the hypothesis, then write the file. You have ${ITERATIONS} iterations
  budgeted — variety of attempts beats depth per attempt.
- Each candidate should take 1-2 minutes total: ~30s to think, ~30s to
  write, ~30-60s for eval to run. If you're spending more than 2 minutes
  thinking about a single candidate before writing, STOP and just write
  something — you can iterate.
- Aim for 4-6 lines of thought max per hypothesis. Bullet form is fine.

## Iteration loop (repeat up to ${ITERATIONS} times)

  1. Quick hypothesis (under 30 seconds of thought).
  2. Write candidates/gen_NNN_description.py IMMEDIATELY.
  3. Run: python eval.py candidates/gen_NNN_description.py --quick
  4. Read the result. If mean Stage-1 c < 1.1, run again without --quick.
  5. Glance at leaderboard; pick next direction; go to 1.

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
