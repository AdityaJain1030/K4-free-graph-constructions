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

1. **Read `insights.md`** to recall what's been learned mathematically.
2. `python leaderboard.py` to see current best and frontier per N.
3. `python show_best.py` to see what's working.
4. Choose your next move using the rules in the next three sections
   (persistent memory, modify-best, crossover), then hypothesize. The
   menu below is a **sample, not a checklist** — favor novelty:
     - Cayley graphs on non-cyclic groups (Z/p × Z/q, dihedral, affine,
       semidirect products, (Z/2)^k)
     - k-th power residues in F_q / F_{p²} / F_{p³}
     - Polarity graphs of projective planes, generalized quadrangles
     - Incidence graphs of Steiner systems, block designs
     - Kneser, Johnson, Hamming, Grassmann graphs
     - Strongly regular graphs from conference / Hadamard matrices
     - Mathon, Paulus, Peisert, twisted Paley variants
     - Strong / tensor / lexicographic products of small K₃-free graphs
     - Vertex blowups, random lifts, voltage graph constructions
     - Hash-defined edges, polynomial-factorization-defined edges
5. Write `candidates/gen_NNN_description.py`.
6. `python eval.py candidates/gen_NNN_description.py --quick` for fast
   signal.
7. If Stage 1 is promising (mean c < ~1.1), run without `--quick` for
   full Stage 2 evaluation.
8. **Append to `insights.md`**: 1–3 lines summarizing the *mathematical*
   pattern you observed (not just the score). See next section.
9. Go to 1.

## After every evaluation: update `insights.md`

Append 1–3 lines to `insights.md` summarizing what you learned. Focus on
MATHEMATICAL patterns, not individual results. Examples:

  "Cubic residues mod p: K4-free for p=13,17,29 but NOT for p=37,41.
   Fails when (p-1)/3 > 12. The connection set gets too dense."

  "Product groups Z/aZ × Z/bZ: regularity is perfect but α scales
   as a·α(C_b, S_b) which is too large. Need connection sets that
   couple the two coordinates."

Read `insights.md` at the start of every session and before choosing
your next family. Do NOT delete or rewrite it — only append.

## When a family already has a candidate scoring below 1.0: modify, don't restart

Do NOT write a new candidate from scratch. Instead:

1. Run `cat candidates/<best_in_family>.py`.
2. Read the code carefully.
3. Make a SPECIFIC, SMALL modification: change one parameter, swap one
   condition in the connection set, try a different prime selection
   strategy, add one filter on the output.
4. Save as a new gen file, cite the parent:
   `# Parent: gen_034 (modified connection set from QR to cubic residues)`

This applies even when rotating to an underexplored family — if that
family has ONE attempt that scored below 1.0, modify it rather than
starting over. Small mutations on good solutions explore the local
neighborhood of what works.

## Every 6th candidate: crossover

Read the source code of the best candidate from TWO DIFFERENT families
(pick the two best-scoring families). Write a new candidate that combines
a structural idea from each. Tag it `# Family: crossover`.

Example: if cayley_cyclic uses quadratic residues on Z/pZ and
cayley_product uses a tensor structure on Z/aZ × Z/bZ, try quadratic
residues on the product group Z/aZ × Z/bZ.

Crossover candidates often fail. That's fine — when they work, they
define new families. Count your crossovers with the `# Family: crossover`
tag; there should be one in every six submissions.

## Family selection rule

Run `python leaderboard.py` and check the **Family status** section at
the top. Each family is tagged one of:

- `UNEXPLORED` — no attempts yet.
- `ACTIVE (underexplored)` — 1 attempt, or still improving with 0 finite scores.
- `ACTIVE` — recent attempts are still improving the family's best.
- `SATURATED` — 3+ consecutive attempts with no improvement to the family's best.
  The leaderboard prints the best candidate's source inline so you can see
  the ceiling without having to `cat` it.

Rules:

- You **MUST NOT** submit candidates to `SATURATED` families unless you
  have a fundamentally different algebraic approach (not a parameter
  tweak, not a connection-set rotation, not a prime-selection change).
  State in your hypothesis comment at the top of the file *why* this is
  structurally different from previous attempts in that family. If your
  justification reduces to "different parameters", pick a different family.
- If any family is `UNEXPLORED`, your next candidate **MUST** target it.
  Pick the one that looks most promising from the menu in the iteration
  loop above.
- Otherwise, prefer `ACTIVE` families with the fewest attempts. That's
  where the signal-per-token is highest.

Every candidate file must carry a `# Family: <name>` header line as its
first or second line so the leaderboard can classify it correctly.
Use one of: `cayley_cyclic`, `circulant`, `cayley_product`,
`cayley_dihedral`, `product`, `polarity`, `gq_incidence`, `kneser`,
`hamming`, `grassmann`, `peisert`, `mathon_srg`, `blowup`, `random_lift`,
`hash`, `latin_square`, `random_greedy`, `crossover`.

## Stopping

If you've tried 20+ candidates without beating the current best score,
stop and report the patterns you see in the data rather than spamming
more variants.
