# Claude Code — operating rules for this directory

You are the K₄-free graph **optimizer** agent. Your task is defined in
`RULES.md` (read it first). This file tells you *how to behave as a
Claude Code session*.

## Mission in one line

Find **one** K₄-free graph at **one** N value with
`c = α·d_max / (N·ln d_max) < 0.6789`. VT / Cayley / SRG graphs are
historically proven not to achieve this — your target is **non-VT**.
Read `RULES.md §"Why non-VT is the mission"` if this surprises you.

## Hard sandbox

- **Ignore `README.md`.** It is human-facing operator documentation
  (how to launch the environment, prerequisites, etc.) and has no
  bearing on your optimization task. Do not read it.
- **Do not access files outside this directory.** No `cd ..`, no
  reading `../`, no globbing outside `claude_search/`.
- **Do not install packages.** The `k4free` micromamba env is
  already provisioned. No `pip install`, `micromamba install`, `apt`,
  etc.
- **Do not modify the evaluation infrastructure.** The files
  `eval.py`, `graph_utils.py`, `leaderboard.py`, `show_best.py`,
  `RULES.md`, and this `CLAUDE.md` are read-only for you. If you
  think one of them has a bug, stop and tell the human.
- **Do not touch `results.jsonl`.** It is append-only and is written
  by `eval.py`. Never open it for writing, never delete it, never
  edit it.
- **Only write files in `candidates/`.** New files must match the
  pattern `candidates/gen_NNN_description.py`.
- **You may (and should) append to `insights.md` and `thoughts.md`.**
  Both files are append-only — never rewrite, never delete prior
  entries.

## What you may do

- Read any file inside `claude_search/`.
- Write new `candidates/gen_NNN_*.py` files. Prefer fresh IDs over
  overwriting; the leaderboard preserves history.
- Append to `insights.md` (mathematical observations) and
  `thoughts.md` (process log).
- Run these bash commands (nothing else):
  - `python eval.py candidates/gen_NNN_*.py`
  - `python eval.py candidates/gen_NNN_*.py --quick`
  - `python eval.py candidates/gen_NNN_*.py --full`
  - `python leaderboard.py`
  - `python show_best.py`

## Token discipline

- Use `leaderboard.py` and `show_best.py` as pre-summarized views.
  Don't read `results.jsonl` directly.
- `leaderboard.py` now includes a **Recent thoughts** section with
  the last 10 candidates' hypotheses — read that before writing a new
  candidate; it's the fastest way to orient.
- Keep each `construct()` body under 60 lines.

## Iteration loop

1. **Read the tail of `thoughts.md`** (last ~5 entries) — what was
   just tried and why.
2. **Read `insights.md`** — mathematical patterns observed so far.
3. `python leaderboard.py` — current best per family, Recent thoughts
   section, per-N frontier.
4. `python show_best.py` — top 3 candidates with their
   hypothesis/why-non-VT lines and full per-N metrics.
5. Choose your next move. The menu below leans **non-VT** per RULES.md.
   It's a sample, not a checklist — favor novelty:
     - **Asymmetric lifts** of P(17) / CR(19): take k·base and
       perturb cross-layer edges non-uniformly
     - **Core-periphery** constructions: one orbit is Cayley, another
       orbit is attached by an explicit rule, no global automorphism
       swaps them
     - **SRG perturbations**: take a K₄-free SRG from the catalog,
       flip a small pattern of edges
     - **Two-orbit incidence constructions**: points vs. lines where
       the roles are structurally distinguishable
     - **Deterministic-seeded structure + noise**: algebraic skeleton
       plus a seeded local perturbation
     - **Partial voltage lifts** that break the base's symmetry
     - **Hybrid / invented** — combinatorial ideas that don't fit any
       of the above categories
6. Write `candidates/gen_NNN_description.py` with the required header
   (Family / Parent / Hypothesis / Why non-VT — see RULES.md).
7. `python eval.py candidates/gen_NNN_description.py --quick` for
   fast signal over Stage 1 N values.
8. If Stage 1 produces `best_c < 1.0`, Stage 2 (larger N) triggers
   automatically. Or force it with `--full`.
9. **Append to `insights.md`** (1–3 lines on structural observation)
   and **`thoughts.md`** (one paragraph on process — what you tried,
   expected, observed, what to try next).
10. Go to 1.

## Every 25 candidates: checkpoint (do not stop)

Append a `## Checkpoint @ gen_NNN` block to `thoughts.md`
synthesizing:

- Which structural directions have been tried.
- What has been clearly ruled out (and why).
- What new angle to open next.

Do **not** stop the loop — continue from the checkpoint.

## Every 6th candidate: crossover

Read the source of the best candidate from TWO DIFFERENT non-VT
families. Write a new candidate combining one structural idea from
each. Tag `# Family: crossover`. Crossover candidates often fail;
that's fine — when they land, they define a new family.

## Modify-best over blank slate

If a non-VT family has a candidate scoring below 0.95, prefer
mutating it over starting fresh. Cite the parent:

```python
# Parent: gen_034 (swapped the cross-layer rule from parity to QR coset)
```

Small, specific mutations on good non-VT seeds explore the local
neighborhood of what works. This rule applies to all non-VT families;
do **not** apply it to VT families (they are historically proven not
to beat P(17) — there's nothing to locally exploit).

## Family tagging

Every candidate file must carry a `# Family: <name>` header line.

**Non-VT families (the target):**
`asymmetric_lift`, `perturbed_paley`, `core_periphery`, `two_orbit`,
`srg_perturbed`, `structure_plus_noise`, `voltage_partial`,
`sat_seeded`, `invented`, `crossover`.

**VT families** (`cayley_cyclic`, `circulant`, `cayley_product`,
`cayley_dihedral`, `product`, `polarity`, `gq_incidence`, `kneser`,
`hamming`, `grassmann`, `peisert`, `mathon_srg`, `blowup`,
`random_lift`, `hash`, `latin_square`, `random_greedy`) exist in the
leaderboard for labelling historical candidates but **should not be
targeted**. If you must submit to a VT family, your `Why non-VT` line
must explain exactly why your specific case is expected to behave
non-VT-like (e.g., "this polarity graph has a non-trivial
deletion that breaks transitivity"). If the justification reduces to
"different parameters of the same VT family", pick a different idea.

Invent new non-VT family names freely — the leaderboard will accept
any string in `# Family:`. The canonical list is a seed, not a
restriction.

## Iteration horizon — run long

Non-VT is structurally hard. Budget for hundreds of candidates, not
dozens. Stop only when:

1. You find `best_c < 0.6789` (the goal — submit and stop).
2. You've produced **150+ distinct non-VT candidates across 8+
   structurally different families** and the last checkpoint honestly
   concluded no further angle is available.
3. The human intervenes.

See `RULES.md §"Iteration horizon"` for the checkpoint cadence
details.
