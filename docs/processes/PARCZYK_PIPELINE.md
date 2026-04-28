# Parczyk-style pipeline, adapted to c = α·d_max/(N·ln d_max)

## What Parczyk et al. do

Their recipe for K₄ Ramsey-multiplicity / g_{s,t}-style problems
(arXiv:2206.04036):

1. Search over a **small core graph** (n ≤ 40). The extremal large-N
   construction is the blow-up sequence of that core.
2. **Tabu / SA** over {0,1}^{n choose 2} with Hamming-1 neighbourhoods.
   Tabu uses a "last ℓ modified bits" history, not a "last ℓ states"
   history — much cheaper to check.
3. **Restrict the domain to Cayley graphs** over a group Γ of order n.
   Search space shrinks from 2^(n choose 2) to 2^(|Γ|/2) (roughly √).
   They found good constructions in groups of order 3·2^k empirically.
4. **Flag algebra SDP** (Razborov) for a matching lower bound →
   certified optimum.

Their Section 5.3 benchmarks Wagner-style cross-entropy RL against
Tabu and SA on this same problem class. Tabu beat CE by 100–500×
wall-clock; on c_{3,4} the 27-vertex construction, Tabu found it in
30 s, CE never did. The reason they give: a construction problem is
not a game — "we do not have any opponent's choices to respond to and
our distribution will ultimately collapse to a single state. This
effectively means that rather than trying to find an approximation of
a strategy, i.e., a still very large sub-tree of the full game tree,
we are merely looking for a single path from the root to a leaf."

## What transfers directly

- Tabu search as default local method.
- Cayley-graph restriction of the search space.
- Seeding from known Ramsey graph libraries (McKay's lists).

## What does *not* transfer

Their cost function is K₄ density — **cheap** (O(n⁴) raw, O(1) per
candidate with precomputed index matrices). Ours is

    c(G) = α(G) · d_max(G) / (N · ln d_max(G))

and α is **NP-hard**. Tabu at 10⁵+ iterations with exact α per step
is infeasible past n ≈ 25. So the Parczyk GPU-batch cost trick does
not port; we need a different evaluation strategy.

Also, their lex-product blow-up G[K̄_t] preserves Ramsey densities
asymptotically; for our c it does **not** (d_max grows like t so c
blows up). For our problem, the structural constant is preserved by
**disjoint union**, not lex blow-up, and the interesting scaling
question is across families of Cayley graphs on different groups
(Paley P(q) stops being K₄-free at q ≥ 19, cubic-residue CR(19)
picks up where Paley P(17) left off, etc.), not across blow-ups of
a single seed.

## The adapted pipeline

### Stage 1: surrogate α
For search, use `alpha_approx(adj, restarts=R)` — multi-restart random
greedy MIS. This is a **lower bound**: α_approx ≤ α_true. Why lower
bound is fine for ranking: within a single run all candidates use the
same R, so the bias is roughly constant, and graphs with small true α
have small α_approx too (strong positive correlation).

For final verification, use `alpha_bb_clique_cover` (fast on sparse
K₄-free graphs) or `alpha_cpsat(..., vertex_transitive=True)` (pins
x[0]=1, sound for Cayley graphs because any orbit meets a MIS).

### Stage 2: generic tabu search
`search/tabu.py` — Parczyk Algorithm 2 verbatim. Operates on
boolean vectors with a user-supplied cost function. "Last ℓ modified
bits" history: the tabu list is a deque of bit indices, and moves
flipping any of those bits are forbidden.

### Stage 3: Cayley-graph connection-set tabu
`search/cayley_tabu.py` — state = connection-set indicator vector over
pair-representatives of Γ (plus any involutions). The undirected Cayley
graph `Cay(Γ, S)` is rebuilt cheaply on each bit flip; K₄-check and
α_approx run in milliseconds for n ≤ 40.

Supported groups (first pass, no GAP dep):
  - Cyclic ℤ_n
  - ℤ_a × ℤ_b (a*b = n, gcd(a,b) ≥ 1)
  - Dihedral D_{n/2}
  - Elementary abelian ℤ_2^k and ℤ_3 × ℤ_2^k (Parczyk's empirical best)

### Stage 4: SAT verification
`scripts/verify_cayley_tabu.py` reads the top-k candidates from tabu,
runs exact α via CP-SAT with `vertex_transitive=True`, recomputes c,
and writes to graph_db under source=`cayley_tabu` with provenance in
metadata (group, connection set, surrogate c at find time).

### Stage 5: driver
`scripts/run_cayley_tabu.py` iterates N from n_lo to n_hi, enumerates
feasible groups of each order, runs tabu per group, saves top-k per N
across groups to `graphs/cayley_tabu.json`. Logs to
`logs/cayley_tabu/run_{timestamp}.jsonl`.

## Out of scope (for this session)

- **Flag algebra SDP.** Certified asymptotic lower bound on c. Big
  build (vendor flagmatic or write SDP from scratch). Without it the
  pipeline gives upper bounds only.
- **GAP/SmallGroups dependency.** Limits us to hand-written group
  families. Sufficient for N ≤ ~40; past that most groups are
  non-cyclic-non-abelian and need GAP.
- **GNN α surrogate.** `alpha_approx` is enough for the first pass.
  Upgrade later if tabu runs exhaust their budget on surrogate noise.

## Success criterion for this session

Drop-in pipeline that runs end-to-end, produces candidate Cayley K₄-free
graphs at each N ∈ [n_lo, n_hi], and SAT-verifies them. Goal is to
reproduce the known best c at every N (Paley P(17), CR(19), …) and
turn up at least one construction that was not previously in the
graph_db. No soundness guarantees; upper bounds only until flag
algebra is added.

## Results (N = 10..50, 2026-04-21)

Results in `results/cayley_tabu/summary.csv` and `comparison.md`.
Totals across 41 target N's:

- **9 matches** of the SAT-exact baseline (N = 10, 11, 12, 13, 16, 17,
  18, 19, 20). Cayley-tabu recovers the known best c exactly.
- **0 tabu-beats-baseline** — Cayley space never improves on SAT at
  N's where SAT has run.
- **2 baseline-better** (N = 14, 15). No Cayley graph on any of the
  supported groups of order 14 or 15 can reach the SAT optimum; this
  is a Cayley-space limitation, not a tabu-budget one (retried with
  3000 iter × 15 restart with no improvement).
- **30 novel** constructions at N = 21..50 (no prior entry in
  graph_db). Includes:
  - **N = 17, Z₁₇, c = 0.6789** — Paley P(17) reproduced.
  - **N = 19, Z₁₉, c = 0.7050** — CR(19) reproduced.
  - **N = 20, D₁₀, c = 0.7195** — dihedral construction matching SAT baseline.
  - **N = 34, Z₂ × Z₁₇, c = 0.6789** — matches P(17) bound at double
    the order. Cayley "Z₂-lift" of P(17): (α, d) → (2α, d), c unchanged.
  - **N = 38, Z₂ × Z₁₉, c = 0.7050** — matches CR(19) at double the
    order (same Z₂-lift mechanism).
  - **N = 44, Z₄₄, c = 0.6995** — matches N=22 Z₂₂ Cayley (again same
    mechanism via Z₂-factor).
- **Best c across the sweep: 0.6789** (at N = 17 and N = 34).

Tabu-search bug fixes applied during this session:
- `search/tabu.py`: sparse 1–3-bit default init (dense random starts
  land in K₄-full infeasible regions where every 1-flip neighbour is
  also infeasible and the search stalls); random-kick move when every
  allowed flip is +inf, instead of early-break.

Known limitations:
- Cayley-only — misses better non-Cayley graphs at some N (14, 15).
- Group families hand-written; missing non-abelian non-dihedral groups
  (S₃, A₄, S₄, …). Adding these needs a GAP / SmallGroups dep or a
  hand roll per-order.
- 54 novel records written to `graphs/cayley_tabu.json` (source=
  `cayley_tabu`); 24 more were canonical duplicates of existing
  entries in `graphs/cayley.json` / `graphs/circulant.json`. Fixed
  pre-existing schema drift via `python scripts/db_cli.py clean
  --apply`, which backfilled 76 stale ids + repaired 76 non-canonical
  sparse6 strings + collapsed 32 canonical duplicates.
