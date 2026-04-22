# Claude Code — operating rules for this directory

You are the K₄-free graph **optimizer** agent. Your task is defined in
`RULES.md`. This file tells you *how to behave as a Claude Code session*.

## Mission in one line

Find **one** K₄-free graph at **one** N value with
`c = α·d_max / (N·ln d_max) < 0.6789`. VT / Cayley / SRG graphs are
historically proven not to achieve this — your target is **non-VT**.

## Your job is translation, not invention

The bottleneck has never been "run local search faster" — it's **finding
good non-VT seed constructions at all**. VT space is exhausted.
Non-VT space has known inhabitants from the literature that have never
been ported here.

`NON_VT_CATALOG.md` lists ten of them. **Work the catalog in the
priority order listed in its "Priority by high-N promise" table.** Each
iteration, pick the next unimplemented entry, port it faithfully as
`construct(N)`, evaluate, append observation.

Do **not** invent a new family. Do **not** start from "take Paley and
modify it". If you want to mutate, mutate an implemented catalog entry
and cite it as `# Parent: gen_NNN` in the header.

## TARGET N ≥ 34 — hard constraint

Every candidate must produce a K₄-free graph with `d_max ≥ 2` at
**some N ≥ 34**. If your construct only works at N ≤ 20, don't submit —
small-N minimizers cannot beat the 0.6789 line because the line itself
is a large-N statement. Prior runs wasted iterations scoring `c ≈ 0.88
at N = 7` which is worthless.

The evaluation grid is `[30, 100]` exactly for this reason. N=7..29 is
not evaluated.

## Hard rules (violation = wasted iteration)

1. **No trivial seed sweeps.** Changing `random.seed(N)` to `random.seed(N*7)`
   in the same code is not a new candidate. Two candidates in the same
   family must differ **structurally** — new edge rule, new algebraic
   base, new perturbation mechanism. If your change is "same code,
   different seed", do not submit it.
2. **At most 2 candidates per catalog entry before moving on.** Port
   once, optionally perturb once with a specific structural hypothesis,
   then move to the next entry.
3. **Mutation requires a specific hypothesis.** `# Parent: gen_NNN (new
   seed)` is banned. `# Parent: gen_NNN (replaced uniform pencil
   bipartition with size-imbalanced 1:2 split)` is OK.
4. **d_max ≥ 2 at some N ≥ 34** or the candidate doesn't count toward
   the iteration budget.

## Hard sandbox

- **Ignore `README.md`.** Human-facing operator doc; not for you.
- **Do not access files outside this directory.** No `cd ..`, no reading
  `../`, no globbing outside `claude_search/`.
- **Do not install packages.** The `k4free` micromamba env is provisioned.
- **Do not modify the evaluation infrastructure.** `eval.py`,
  `graph_utils.py`, `leaderboard.py`, `show_best.py`, `RULES.md`,
  `NON_VT_CATALOG.md`, and this `CLAUDE.md` are read-only for you. If
  you think one of them has a bug, stop and tell the human.
- **Do not touch `results.jsonl`.** Append-only, written by `eval.py`.
- **Only write files in `candidates/`.** New files must match the
  pattern `candidates/gen_NNN_<description>.py`.
- **Append-only for `insights.md` and `thoughts.md`.** Never rewrite,
  never delete prior entries.

## What you may do

- Read any file inside `claude_search/`.
- Write new `candidates/gen_NNN_*.py` files. Prefer fresh IDs over
  overwriting.
- Append to `insights.md` and `thoughts.md`.
- Run these bash commands (nothing else):
  - `python eval.py candidates/gen_NNN_*.py`
  - `python eval.py candidates/gen_NNN_*.py --quick`
  - `python eval.py candidates/gen_NNN_*.py --full`
  - `python leaderboard.py`
  - `python show_best.py`

## Iteration loop

1. `python leaderboard.py` — shows best per family, recent thoughts
   (last 10 hypotheses), per-N frontier. **This replaces reading
   `thoughts.md` and `insights.md` separately.** Do not re-read those
   unless you're specifically planning to mutate a parent (then read
   `show_best.py`).
2. Open `NON_VT_CATALOG.md`. Find the next entry that doesn't yet have
   a candidate file citing it. Work entries in the order listed under
   §"Work order" unless a prior one has been ruled out.
3. Write `candidates/gen_NNN_<entry_tag>.py`. The header must include
   `# Catalog: <entry_tag>` so the leaderboard can track coverage.
4. `python eval.py candidates/gen_NNN_*.py --quick` — fast signal.
5. If Stage 1 produces `best_c < 1.0`, Stage 2 triggers automatically
   (or force with `--full`).
6. Append **one short line** to `insights.md` if the eval told you
   something structural you didn't already know from the catalog
   (e.g., "ER(5) hits α=11 at N=31, above the theoretical q^{3/2}=11.2,
   so ER is essentially Hoffman-tight"). If the eval result is
   unsurprising, skip the insight — don't write for the sake of writing.
7. Append **one short paragraph** to `thoughts.md` only if you're
   about to mutate or if you need a process note for future-you. Skip
   for routine catalog ports.
8. Go to 1.

## When to mutate instead of porting

A mutation = modifying an already-implemented catalog entry (small,
deterministic perturbation — an edge flip rule, degree cap, seed sweep).

Mutate when:
- Every catalog entry has at least one faithful port.
- OR an entry's initial port scored below c=0.95 and you have a
  specific structural hypothesis for what perturbation would lower it
  further. Cite as `# Parent: gen_NNN (<one-line mutation description>)`.

Do **not** mutate:
- After a catalog entry produced `c > 1.2` — that's the family saying
  "not competitive", move to the next catalog entry.
- By introducing Paley as a base. Paley is structurally disallowed as
  a scaffold in this session.

## Family tagging

Every candidate file must carry two header lines:

```
# Family: <family_tag>      # the broad family (e.g. polarity, incidence, random_process)
# Catalog: <entry_tag>      # which NON_VT_CATALOG.md entry this implements
```

For mutations, add `# Parent: gen_NNN` as well.

## Token discipline

- Use `leaderboard.py` as the primary orient. It has the recent-thoughts
  excerpt; you don't need separate `Read` calls on `thoughts.md`.
- `show_best.py` only when about to mutate a parent.
- Keep each `construct()` body under 60 lines.
- Keep hypothesis/why-non-VT header lines under ~40 words each. The
  catalog entry already contains the structural reasoning — your header
  just says "I implemented entry X with these specific parameter
  choices."

## Iteration horizon — 200 candidates

This session runs for **at least 200 distinct candidates**. Do not stop
early. Stop only when:

1. You find `best_c < 0.6789` (the goal — submit and stop).
2. You have produced 200 candidates that each passed the "d_max ≥ 2 at
   some N ≥ 34" constraint. At that point write a final summary in
   `thoughts.md` and stop.
3. The human intervenes.

Candidates that don't produce d_max ≥ 2 at any N ≥ 34 (e.g. your code
only works at N = 7) **do not count** toward the 200. Track your count
in `thoughts.md` checkpoints at gen_050, gen_100, gen_150.
