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
- Study `results.jsonl` (append-only JSON lines) for full history of
  every attempt, including failures.

## Scoring

- **Primary score** = mean(finite c values over Stage 1 N values)
  + 0.001 × `code_length`. **Lower is better.**
- Stage 1 N values: `[20, 25, 30, 40, 50, 60]`.
- Stage 2 (triggered if Stage 1 mean c < 1.5) evaluates additional N
  values up to 75 by default (100 with `--full`).
- `score_full` = same formula across ALL evaluated N values (only set
  if Stage 2 ran).
- `score_regularity` = mean `regularity_score` (1.0 = perfectly regular).
  Tracked separately; not part of the primary score but is the single
  strongest predictor of good c.
- The **code-length penalty** (0.001 × chars) means: if two constructions
  tie on c, the shorter/more algebraic one wins.

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
- **Cayley graphs** on finite groups are automatically regular. The group
  action ensures every vertex has the same neighborhood structure.
  The Paley graph is Cayley on (Z/pZ, +) with connection set = QRs.
- **Circulant graphs** C(N, S) are Cayley on Z/NZ. They're N-vertex
  |S|-regular (with |S| symmetric, i.e. s ∈ S ⇔ −s ∈ S). The challenge is
  choosing S so the graph is K₄-free at the target N.
- **Algebraic connection sets** (quadratic residues, cubic residues,
  subgroups of multiplicative groups) tend to produce K₄-free graphs
  much more often than random sets.
- **Don't bother with:** random edge-by-edge construction, degree-capped
  random graphs, brute-force adjacency-matrix search. All plateau near
  c ≈ 0.94 or are too slow.
- **Handle non-prime N.** If your construction only works at N = p prime,
  you'll score poorly at most Stage 1 N values. Consider: extending to
  Z/pq, bipartite/join composition, vertex-blowup, strong products.
- **Study `results.jsonl`.** Every prior attempt is recorded with full
  metrics. Look for patterns: which N values are hard? Which constructions
  have high regularity but still bad c (then α is the bottleneck)?
  Which have low α but bad regularity?

## Rules

- Only modify files in `candidates/`. Do not touch `eval.py`, `leaderboard.py`,
  `show_best.py`, `graph_utils.py`, or `results.jsonl`.
- Allowed imports in candidate files: `math`, `random`, `itertools`, `numpy`.
- If you use randomness, seed it: `random.seed(42)` or `numpy.random.seed(42)`.
- Keep `construct()` body under 50 lines. Algebraic/concise is rewarded by
  the code-length penalty.
- Name files descriptively: `gen_042_cayley_cubic_residues.py`, not
  `gen_042.py`.
- Edges are **undirected**: return each edge once. Duplicates are harmless
  (edges_to_adj de-dupes) but clutter your source.
- Vertices are **0-indexed**: return integers in [0, N).
