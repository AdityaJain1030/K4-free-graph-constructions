# Rules for the K₄-Free Graph Optimizer

You are an optimizer agent. Your job is to evolve a `construct(N)` function
that builds K₄-free graphs minimizing:

```
c = α(G) · d_max / (N · ln(d_max))
```

## The problem

- A graph is **K₄-free** iff no 4 of its vertices are pairwise adjacent.
  Equivalently, every vertex's neighborhood induces a triangle-free subgraph.
- **α(G)** is the independence number — the size of the largest set of
  pairwise non-adjacent vertices. Computed here exactly via SAT
  (falls back to a greedy lower bound if SAT times out).
- **d_max** is the maximum degree.
- **Baseline:** the Paley graph **P(17)** — the Cayley graph on Z/17Z with
  connection set = quadratic residues mod 17 — is 8-regular, K₄-free, has
  α=3, and achieves **c ≈ 0.6789**. Beating this is the target.
- Heuristic/greedy methods plateau near c ≈ 0.94 because they produce
  irregular degree sequences. The ~25% gap to P(17) is almost entirely
  explained by **degree irregularity**.

## How to work

- Write a file to `candidates/gen_XXX_description.py` containing:
  ```python
  def construct(N: int) -> list[tuple[int, int]]:
      """Return edge list for a K4-free graph on N vertices (0-indexed)."""
      ...
  ```
- Run `python eval.py candidates/gen_XXX_description.py` to evaluate
  (Stage 1 + Stage 2 cascade if Stage 1 passes).
- Run `python eval.py candidates/gen_XXX_description.py --quick` for
  fast iteration (Stage 1 only).
- Run `python eval.py candidates/gen_XXX_description.py --full` to
  force Stage 2 up to N=100.
- Run `python leaderboard.py` to see standings.
- Run `python show_best.py` to inspect source + full per-N metrics for
  the top 3.

## Discovery model — evolution, not blank slate

This search is **evolutionary**, not independent. Each candidate should
build on accumulated knowledge, not start from scratch. Three mechanisms,
enforced by `CLAUDE.md`:

1. **Persistent memory (`insights.md`).** Every evaluation ends with you
   appending 1–3 lines of *mathematical* observation (not score): which
   primes worked, which density threshold failed, which group structure
   caused K₄s. Read it at the start of every cycle. Mistakes you make
   without consulting it will be repeats of prior mistakes.

2. **Modify-best over blank-slate.** If a family already has a candidate
   scoring below 1.0, do NOT rewrite that family from scratch. `cat` the
   parent, make one small change (swap QR for cubic residues, change
   prime selection, add one filter), and cite `# Parent: gen_XXX` in the
   new file's header. Mutations on known-good solutions explore the
   local neighborhood of what works.

3. **Crossover every 6th candidate.** Read the two best-scoring families'
   source and combine a structural idea from each (e.g., QR connection
   set on a product group). Tag `# Family: crossover`. Most crossovers
   fail; when they land, they define a new family.

The three together implement explore/exploit: insights.md is memory,
modify-best is local exploitation, crossover is directed exploration.

## Scoring

- **Primary score** = mean(finite c values over Stage 1 N values)
  + 0.001 × `code_length`. **Lower is better.**
- **Partial-N constructions are welcome.** The mean is taken only over N
  where your construct returned a valid K₄-free graph (failures are
  dropped, not averaged as infinity). A construction that only works at
  N ∈ {q² + q + 1 : q prime power} or N ∈ {primes ≡ 1 mod 4}, but scores
  c = 0.5 at those N, will easily beat a construction that works
  everywhere averaging c = 0.8. **Finding an infinite family that
  achieves c → constant < 0.6789 is the goal; covering every N in
  Stage 1 is not.** Return `[]` or let construct raise for N outside
  your family's sweet spot.
- Stage 1 N values: every integer in `[7, 60]` (54 values). The signal is
  how your construction behaves as a function of N, not just at a handful
  of points. N=17 is included but will not trivially reward P(17) copies
  because the penalty is mean over all 54 N.
- Stage 2 (triggered if Stage 1 mean c < 1.5) evaluates additional N
  values up to 75 by default (100 with `--full`).
- `score_full` = same formula across ALL evaluated N values (only set
  if Stage 2 ran).
- `score_regularity` = mean `regularity_score` (1.0 = perfectly regular).
  Tracked separately; not part of the primary score but is the single
  strongest predictor of good c.

## Metrics you'll see

| field | meaning |
|---|---|
| `c` | the objective. Lower is better. P(17) = 0.6789. |
| `regularity_score` | 1.0 = all vertices same degree. <0 means very skewed. |
| `alpha` | independence number. Exact if `alpha_exact=true`, else greedy lower bound. |
| `d_max` / `d_min` / `d_mean` | degree stats. |
| `edge_count` / `edge_density` | sanity. |
| `triangle_count` | diagnostic. K₃'s are allowed; K₄'s are not. |
| `is_connected` | disconnected graphs usually hurt α. |
| `failure_reason` | why this N scored infinity. |

## `failure_reason` values

- `"timeout"` — construct(N) took >5s.
- `"crash: <ExcType>: <msg>"` — construct raised an exception.
- `"invalid_edge_format"` — return value wasn't a list of (i,j) int tuples.
- `"d_max_too_low"` — max degree < 2; degenerate.
- `"not_k4_free"` — a neighborhood contains a triangle.
- `"syntax_error: ..."` — file can't even be imported.
- `"import_error: ..."` / `"construct_not_found: ..."` — module issues.

Read these. A stream of `not_k4_free` failures tells you to rethink
your edge selection; `timeout` means your algorithm is too slow for N=60.

## Strategy hints (read these)

- **Regularity is everything.** Random/greedy methods fail not because
  they can't find K₄-free graphs, but because the degree sequence they
  produce is uneven. Focus on constructions that are regular **by design**.
- **Explore diverse algebraic families.** Quadratic/cubic residues in
  F_q, subgroups of multiplicative groups, polarity graphs of projective
  planes, incidence structures of Steiner systems, generalized quadrangles,
  strong/tensor products of small graphs, vertex-blowups, Cayley graphs on
  non-cyclic groups (Z/p × Z/q, dihedral, semidirect products).
- **Study `leaderboard.py` and `show_best.py` output.** Look for patterns:
  which N values are hard? Which constructions have high regularity but
  still bad c (then α is the bottleneck)? Which have low α but bad
  regularity?

## Rules

- Only modify files in `candidates/`. Do not touch `eval.py`, `leaderboard.py`,
  `show_best.py`, `graph_utils.py`, or `results.jsonl`.
- Allowed imports in candidate files: `math`, `random`, `itertools`, `numpy`.
- If you use randomness, seed it: `random.seed(42)` or `numpy.random.seed(42)`.
- Keep `construct()` body under 50 lines. Algebraic/concise is rewarded.
- Name files descriptively: `gen_042_cayley_cubic_residues.py`, not
  `gen_042.py`.
- Edges are **undirected**: return each edge once. Duplicates are harmless
  (edges_to_adj de-dupes) but clutter your source.
- Vertices are **0-indexed**: return integers in [0, N).
