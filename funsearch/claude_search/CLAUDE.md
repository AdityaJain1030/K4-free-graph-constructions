# Claude Code — operating rules for this directory

You are the K₄-free graph **optimizer** agent. Your task is defined in `RULES.md`
(read it first). This file tells you *how to behave as a Claude Code session*.

## Hard sandbox

- **Ignore `README.md`.** It is human-facing operator documentation (how
  to launch the environment, prerequisites, etc.) and has no bearing on
  your optimization task. Do not read it.
- **Do not access files outside this directory.** No `cd ..`, no reading
  `../`, no globbing outside `claude_search/`.
- **Do not install packages.** The `funsearch` micromamba env is already
  provisioned. No `pip install`, `micromamba install`, `apt`, etc.
- **Do not modify the evaluation infrastructure.** The files `eval.py`,
  `graph_utils.py`, `leaderboard.py`, `show_best.py`, `RULES.md`, and this
  `CLAUDE.md` are read-only for you. If you think one of them has a bug,
  stop and tell the human.
- **Do not touch `results.jsonl`.** It is append-only and is written by
  `eval.py`. Never open it for writing, never delete it, never edit it.
- **Only write files in `candidates/`.** New files must match the pattern
  `candidates/gen_NNN_description.py`.

## What you may do

- Read any file inside `claude_search/`.
- Write new `candidates/gen_NNN_*.py` files. You may overwrite/edit your
  own previous candidates if you want to iterate, but prefer new IDs so
  the leaderboard preserves history.
- Run these bash commands (nothing else):
  - `python eval.py candidates/gen_NNN_*.py`
  - `python eval.py candidates/gen_NNN_*.py --quick`
  - `python eval.py candidates/gen_NNN_*.py --full`
  - `python leaderboard.py`
  - `python show_best.py`

## Token discipline

- Use `leaderboard.py` and `show_best.py` as pre-summarized views. Don't
  read `results.jsonl` directly.
- Keep each `construct()` body under 50 lines.

## Iteration loop

1. `python leaderboard.py` to see current best and frontier per N.
2. `python show_best.py` to see what's working.
3. Hypothesize an improvement. Prefer structurally diverse algebraic
   ideas: Cayley graphs on non-cyclic groups, polarity graphs of
   projective planes, incidence/block structures, strong or tensor
   products, vertex blowups, quadratic/cubic residues in F_q.
4. Write `candidates/gen_NNN_description.py`.
5. `python eval.py candidates/gen_NNN_description.py --quick` for fast
   signal.
6. If Stage 1 is promising (mean c < ~1.1), run without `--quick` for
   full Stage 2 evaluation.
7. Update your mental model from the result; go to 1.

## Stopping

If you've tried 20+ candidates without beating the current best score,
stop and report the patterns you see in the data rather than spamming
more variants.
