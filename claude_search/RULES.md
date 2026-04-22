# Rules for the K₄-Free Graph Optimizer

## Read NON_VT_CATALOG.md first

`NON_VT_CATALOG.md` is the **primary source of constructions**. Your job
is to port the entries it lists — not to invent new families. "Invent a
non-VT graph" failed in prior sessions because the model anchors on
Paley; "port the Mattheus–Verstraete construction" is a concrete
translation task the LLM can do well. Work the catalog. See
`CLAUDE.md §"Iteration loop"` for the exact per-iteration procedure.

## The target

Find **one** K₄-free graph on **one** N that achieves

```
c(G) = α(G) · d_max(G) / (N · ln(d_max(G)))  <  0.6789
```

That's it. Not a family, not a construction that works everywhere, not a
low mean across many N. A single `(N, G)` pair that crosses the Paley
threshold is a 30-year record break.

A construction that returns `[]` for every N except one and produces
`c = 0.65` at that one N is a **winning** submission. Scoring treats
dropped N as "not attempted" — you are not penalized for narrowness.

## Why non-VT is the mission

Every Paley-beater attempt in this repo so far stays inside the
vertex-transitive (VT) space: Cayley residues, Cayley tabu over every
supported group of order N, exhaustive cyclic lift verification, and a
full screen of McKay's SRG catalog (4,361 graphs — zero beaters). They
all stop at `c ≥ 0.6789`.

The structural reason is the **Lovász theta identity**: for every
vertex-transitive G, `θ(G) = α(G)` exactly. For non-VT G, generically
`θ(G) > α(G)` — the SDP is slack and α can slip below what symmetry
would enforce. Smaller α at fixed degree means smaller `c`.

**So the break, if it exists, lives outside VT space.** Your job is to
build graphs that are *not* Cayley, *not* SRG, *not* circulant — graphs
whose automorphism group does **not** act transitively on vertices. VT
candidates have been proved not to help here; don't submit them.

## What non-VT looks like in practice

VT shows up as:

- Cayley graphs `Cay(Γ, S)` for any group Γ and symmetric set S
- Circulants (Cayley on ℤ_n)
- Most named SRGs, generalized quadrangles, Kneser/Johnson/Hamming
- Tensor / lex / strong products of VT factors
- Vertex-blowups of VT graphs

Non-VT shows up as:

- **Asymmetric perturbations of VT graphs** — start from k·P(17) and add
  or swap a small non-uniform set of cross-layer edges
- **Core-periphery / two-orbit constructions** — a graph where some
  vertices are structurally different from others
- **Incidence-like constructions where points and lines have
  different roles and aren't swapped by any automorphism
- **Deterministic structure plus deterministic-seeded perturbation**
- **Partial voltage lifts** — the lift breaks the base's symmetry
- **Local modifications of SRGs** — the McKay screen found 13 K₄-free
  SRGs; perturb one locally
- **Invented constructions** not in any of the above categories

If your construction can be written as `Cay(Γ, S)`, it is VT. Keep
going.

## Focus on constructions, not N

**Your job is to invent a structural idea — let the pipeline decide
which N it helps at.** Write `construct(N)` so it accepts every
integer N the eval grid sends (7 through 150). Don't hardcode it to a
single N, don't gate with `if N != 34: return []` unless that gate is
a genuine structural part of the idea (e.g., "only defined when N is
a prime ≡ 1 mod 4"). If your construction is only meaningful at
certain N, it's fine — just return `[]` at the rest and let the
pipeline record where your idea lands. Think about the *construction*,
not about *which N to target*.

Context on the N landscape (informational, not a targeting list):

- **Small N (≤ 20)** is already solved by SAT-exact. Whatever c your
  construction produces there matches known bounds or doesn't — it
  doesn't distinguish you. You are not trying to reproduce P(17).
- **Medium-to-large N (34, 51, 68, 85, and 40–150)** is where the
  current Cayley frontier hasn't been broken. A Paley-beater most
  plausibly lives here because the combinatorial space is large
  enough to admit asymmetric constructions.
- **Projective-plane orders** (N ∈ {13, 31, 57, 73, 91, 133, ...})
  have dominant VT polarity graphs; a non-VT perturbation there is
  publishable.

A single (N, G) pair with c < 0.6789 wins — at *any* N. Returning `[]`
everywhere except where your idea makes sense is correct, not
incomplete.

## Candidate file format

Every file `candidates/gen_NNN_description.py` must start with this
header block, in this order, all four fields required:

```python
# Family: <family_tag>      # broad family, e.g. polarity, incidence, random_process
# Catalog: <entry_tag>      # which NON_VT_CATALOG.md entry this implements
# Parent: gen_XXX           # or "none" if this is a fresh port from the catalog
# Hypothesis: <1-2 sentences on what this implementation does and what you expect>
# Why non-VT: <1-2 sentences on what breaks vertex-transitivity>

def construct(N: int) -> list[tuple[int, int]]:
    """Return edge list for a K4-free graph on N vertices (0-indexed)."""
    ...
```

The `Hypothesis` and `Why non-VT` lines are the permanent record of
your reasoning and are logged automatically. Do not skip them. If a
future candidate wants to mutate yours, it reads your header to decide
whether to.

## How to work

- `python eval.py candidates/gen_NNN_*.py` — full eval (Stage 1 + Stage 2 if promising).
- `python eval.py candidates/gen_NNN_*.py --quick` — Stage 1 only, fast feedback.
- `python eval.py candidates/gen_NNN_*.py --full` — force Stage 2 up to N=100.
- `python leaderboard.py` — best-c per family, last 10 hypotheses, status.
- `python show_best.py` — top 3 by best_c with full per-N metrics.

## Discovery model

Evolutionary, not blank-slate:

1. **`insights.md`** (mathematical patterns) — at the start of every
   cycle, read it. At the end of every cycle, append 1–3 lines on the
   *structural* observation: which N failed K₄-freeness, which
   perturbation pattern broke α, which combinatorial invariant
   correlates with low c.

2. **`thoughts.md`** (agent process log) — append a paragraph per
   candidate. What were you trying? What did you expect? How did the
   result line up with expectation? This is the record of *why* you
   chose what you chose — counterpart to insights.md focused on
   reasoning, not math.

3. **Modify-best.** If a non-VT candidate scored below 0.95, consider
   mutating it before starting a new family. Small changes on good
   non-VT seeds are worth more than fresh cold starts on known-bad
   families.

4. **Crossover.** Every sixth candidate, combine one idea from each of
   the two best non-VT candidates. Tag `# Family: crossover`.

All three files — `insights.md`, `thoughts.md`, `candidates/` — are
append-only. Never rewrite or delete prior entries.

## Scoring — pure minimization

Primary score: **`best_c`** = the single minimum c across every N
where your construct returned a valid K₄-free graph with `d_max ≥ 2`.
Lower is better. **No averaging, no breadth penalty.**

```
score = best_c + 0.001 · code_length      # code_length is only a tiebreaker
```

- **Drop-on-failure semantics**: N values where construct raised,
  timed out, returned bad edges, returned a K₄-containing graph, or
  returned a graph with `d_max < 2` are *dropped* — they do not hurt
  your score. Returning `[]` for N outside your sweet spot is the
  correct move.
- **A single (N, G) winner is the goal.** A candidate that succeeds
  at exactly one N — any N — with `c < 0.6789` wins the whole
  project. Breadth is neither rewarded nor penalized.
- `score_mean` and `score_full` are recorded as diagnostics only,
  for visibility into a candidate's breadth. They do not affect
  ranking.

## N grid

Stage 1 evaluates **every integer N in [30, 100]**. Small N is excluded
deliberately: the Paley threshold is a large-N statement, and prior
runs spent compute on N ≤ 20 minimizers that cannot generalize. Your
construction must produce d_max ≥ 2 at some N ≥ 34 to be meaningful.
N values where your construct returns `[]` are essentially free
(fast-fail at `d_max_too_low`).

Stage 2 (triggered when Stage 1 `best_c < 1.0`, or forced with
`--full`) extends to N ∈ {110, 120, 133, 150}. Use `--quick` for
Stage-1-only when iterating fast; full or automatic for real runs.

## Rules

- Only modify files in `candidates/`. Exceptions: **append** (never
  rewrite) to `insights.md` and `thoughts.md`.
- Do not touch `eval.py`, `leaderboard.py`, `show_best.py`,
  `graph_utils.py`, `results.jsonl`, `RULES.md`, `CLAUDE.md`.
- Allowed imports: `math`, `random`, `itertools`, `functools`,
  `collections`, `numpy`, `sympy`.
- Seed any randomness: `random.seed(...)` or `numpy.random.seed(...)`.
- `construct()` body ≤ 60 lines. Algebraic / geometric concision is
  preferred over ad-hoc verbosity.
- Edges undirected, vertices 0-indexed in `[0, N)`.
- **VT submissions are historically proven not to beat Paley.** If you
  submit something that can be written as `Cay(Γ, S)` or that has a
  transitive automorphism group, your `Why non-VT` line must explain
  exactly why your case is expected to behave differently — and if it
  reduces to "different parameters of the same family", pick a
  different idea.

## Failure reasons (from `eval.py`)

| reason                | what it means                                              |
|-----------------------|------------------------------------------------------------|
| `timeout`             | construct(N) took > 5 s                                    |
| `crash: ...`          | construct raised                                           |
| `invalid_edge_format` | return value wasn't a list of (i, j) int tuples            |
| `d_max_too_low`       | max degree < 2 (including N where you returned `[]`)       |
| `not_k4_free`         | some neighborhood contains a triangle                      |
| `syntax_error: ...`   | file can't be imported                                     |
| `alpha_crash: ...`    | α solver crashed (rare; usually a malformed graph)         |

A stream of `not_k4_free` tells you to rethink the edge rule. A stream
of `d_max_too_low` is expected and correct if you're targeting a narrow
N range.

## Iteration horizon — run long

Non-VT is structurally hard. Every known K₄-free extremizer historically
was built VT-first; the tools for reasoning about non-VT are weaker,
and good non-VT constructions will not fall out of a few dozen
attempts. **Budget for hundreds of candidates, not dozens.** Do not
stop early.

Checkpointing instead of stopping:

- **Every 25 candidates**: append a "Checkpoint" section to
  `thoughts.md` synthesizing (a) which structural directions have been
  tried, (b) which clearly ruled out, (c) what new angle to open next.
  Do not stop — continue from the checkpoint.
- **Every 50 candidates**: re-read the full `insights.md` and
  `thoughts.md` tail, look for recurring patterns you hadn't noticed
  locally, and commit to a direction shift if the last 25 entries show
  no structural novelty.

Stop only when one of:

1. You find a graph with `c < 0.6789` (the goal — submit and stop).
2. You've produced at least **150 distinct non-VT candidates** across
   **at least 8 structurally different families**, and the last
   checkpoint honestly concluded no further non-VT angle is available.
   At that point write a final summary in `thoughts.md` and stop.
3. The human intervenes.

"Structurally different families" means the underlying mechanism is
different, not just the parameters. `perturbed_algebraic` with 1 swapped
edge and `perturbed_algebraic` with 5 swapped edges are the same family;
`perturbed_algebraic` and `core_periphery` are different families.

If you find yourself repeating variants of the same idea, that's a
signal to invent, not to stop.
