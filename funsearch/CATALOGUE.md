# FunSearch Experiments — Catalogue

This document records the conceptual background, experimental design, findings,
and conclusions for each experiment run under `funsearch/experiments/`. The
overall goal throughout was to discover K₄-free graph construction algorithms
that push `c_log = α·d_max / (N·ln(d_max))` below the P(17) benchmark of
**0.679**.

---

## Background: Why FunSearch?

The direct approach — just enumerate or SAT-optimize graphs — works at small N
but breaks down above N ≈ 30. FunSearch (DeepMind, Nature 2024) offers an
alternative: instead of searching for *graphs*, evolve *construction algorithms*
`construct(N) → edge_list`, and use an LLM in an evolutionary loop to improve
them. DeepMind applied this to cap sets; the idea is the same here.

The K₄-free constraint fits naturally: a graph is K₄-free if and only if every
vertex's neighborhood is triangle-free. So any greedy edge-addition procedure
can check K₄-freeness locally and cheaply (O(d²) per edge) without global
reasoning. The LLM only needs to learn a good priority function — which vertex
to connect to next — and the skeleton handles the hard constraint automatically.

---

## Core Concepts

### The Block Library

A **block** is a small K₄-free graph (n ≤ 8 in most experiments here). The
block library is the complete set of all such graphs, enumerated exhaustively
via `nauty geng` and deduplicated by canonical isomorphism class. At n ≤ 8
this gives 83 distinct blocks with meaningful structure. The idea is that
large good graphs might be built by composing small blocks — if the optimal
structure factorizes, then the search space is much smaller.

### α-Dropping Sets

An independent set S in a graph G is **α-dropping** if removing S from G
(i.e. taking the induced subgraph on V \ S) drops the independence number:
`α(G[V\S]) = α(G) − 1`. Intuitively: S is a "tight" IS whose removal
forces the rest of the graph to have a smaller maximum IS.

Not all independent sets are α-dropping. For a graph like P(17), which is
close to vertex-transitive, no single vertex is forced into every max-IS —
so single-vertex sets are not α-dropping. This turns out to be a deep
structural fact about good graphs.

Why do α-dropping sets matter? They are the connectors in IS-join composition.

### IS-Join (Independent-Set Join)

Given two graphs A and B, with an α-dropping set S_A ⊆ A and S_B ⊆ B, the
**IS-join** is the graph formed by:
1. Taking the disjoint union of A and B.
2. Adding a complete bipartite graph between S_A and S_B (every vertex in S_A
   is connected to every vertex in S_B).

The key arithmetic property: if S_A and S_B are α-dropping, then:

```
α(IS-join(A, B)) = α(A) + α(B) − 1
```

This is exact at depth 1 — no SAT call needed. The independence number of
the composed graph is a deterministic function of the two blocks and their
dropping sets. The max degree is also computable analytically: interior
vertices keep their original degree, connector vertices (those in S_A or S_B)
gain `|S_B|` or `|S_A|` new neighbors respectively.

This gives an instant, exact `c_log` score for any composition, which was
the main motivation: if large graphs decompose this way, we get a massively
accelerated search with no SAT calls in the inner loop.

### Composition Depth

**Depth** is how many rounds of IS-join you apply:

- **Depth 1:** Join two library blocks directly. The arithmetic formula
  `α(A) + α(B) − 1` is provably exact. `c_log` is a closed-form function
  of the two blocks and their dropping sets — no SAT needed.

- **Depth 2:** Join two depth-1 composed graphs. The formula says
  `α(comp1) + α(comp2) − 1`, but this is now wrong. Max independent sets
  in the result can route across internal block boundaries in ways the
  formula doesn't see, so the computed α drifts below the true α.

- **Depth N (single vertices as blocks):** Every block is one vertex.
  IS-joining them one at a time is just greedy edge addition with a
  complete-bipartite wiring rule. Fully expressive, but the arithmetic
  shortcut is completely gone — you need SAT to score anything.

Depth is a dial between two extremes: low depth gives exact scoring but
limited expressiveness; high depth is fully expressive but requires SAT
and loses the main advantage of the block approach. Experiment 8 ablated
this dial directly and found that going deeper was uniformly worse — the
arithmetic error accumulates without any compensating gain in graph quality.

### Edge Trimming

Given a graph G, **edge trimming** removes edges greedily as long as α(G)
doesn't increase. The result is an **α-critical graph** — every remaining
edge is essential (removing any edge increases α). α-critical graphs are
the "tightest" K₄-free graphs at a given (N, α): same independence number
with fewer edges means lower d_max and thus better c_log.

The trimming procedure shuffles edges, tries removing each one, and discards
the edge if α is unchanged (using exact branch-and-bound for n ≤ 20, SAT for
larger). It's stochastic in its edge ordering but deterministic in its output
given a seed.

---

## Experiments

### Experiment 1 — Initial Validations (`experiments/initial_validations/`)

**Question:** Is SAT evaluation fast enough for inner-loop scoring? Does
sequential vertex-by-vertex construction work at all?

**What we found:**
- SAT is trivially fast: mean < 0.4 sec at N=40–80, zero timeouts.
- Greedy MIS is an excellent proxy for true α (Spearman ρ = 0.99). Caro–Wei is not (ρ = 0.52).
- **Vertex-by-vertex construction is broken:** early vertices accumulate all
  edges, creating star graphs with c = 2.9–17.6. No priority function fixes
  this — the structural degree gradient is inherent to the approach.
- Random edge addition with degree cap achieves c ≈ 1.1–1.2, flat over N=40–80.

**Conclusion:** Vertex-by-vertex is dead. Use edge-based construction with
degree cap. SAT evaluation is fast enough; greedy MIS suffices as a proxy.

---

### Experiment 2 — Block Decomposition (`experiments/block_decomposition/`)

**Question:** Can we compose small K₄-free blocks via IS-join to build larger
good graphs? Does the arithmetic α formula hold in practice?

**Setup:** Build a library of all K₄-free graphs with n ≤ 8 (83 blocks total,
593 α-dropping sets across them). Enumerate all valid depth-1 IS-join
compositions (~351,649 pairs, scored in 5 min). SAT-verify the top 50.

**What we found:**

| N | Best c (IS-join) | SAT-optimal c | Gap |
|---|-----------------|---------------|-----|
| 10 | 0.866 | ~0.77 | +12% |
| 13 | 0.888 | 0.773 | +15% |
| 16 | 0.902 | 0.721 | +25% |
| 21 | 0.888 | 0.733 | +21% |

- Arithmetic α formula confirmed correct on all 10 SAT-verified compositions.
- Beats random edge construction (c ≈ 1.2) but sits 15–25% above SAT-optimal.
- **The SAT-optimal N=16 graph has zero valid IS-join decompositions** across
  all 2^16 vertex partitions. Optimal graphs are structurally non-compositional.

**Conclusion:** IS-join's complete-bipartite seam is a fundamental bottleneck.
Optimal graphs don't decompose as IS-joins of n ≤ 8 blocks.

---

### Experiment 3 — Edge Trimming (`experiments/block_decomposition/trimming/`)

**Question:** Can trimming the IS-join compositions close the gap to SAT-optimal?
Are SAT-optimal graphs α-critical (hence reachable by trimming)?

**What we found:**
- Trimming improved c by 0–7% only. Meaningful only at N=21 (d_max 5→4).
- α-critical graphs have zero α-dropping sets — once you trim to α-critical,
  the iterative enrichment pipeline (compose → verify → re-add to library) is
  impossible. Trimming and re-composition are structurally incompatible.
- **SAT-optimal graphs are NOT IS-join decomposable**, even post-trimming.

**Conclusion:** Trimming is a dead end within this framework. The IS-join seam
is the fundamental bottleneck, not edge density.

---

### Experiment 4 — Block Optimal (`experiments/block_optimal/`)

**Question:** Can any combination of n ≤ 8 blocks reach the SAT-optimal
(α, d_max) pairs at N=17–21 via IS-join?

**What we found:**
- Zero feasible compositions at N=17, 18, 19, 20, 21.
- The (α, d_max) regime of SAT-optimal graphs (e.g. α=4, d_max=6 at N=18)
  is unreachable from the n ≤ 8 library. You'd need blocks up to n ≈ 17
  to cover that regime — at which point you're just directly optimizing
  large graphs.

**Conclusion:** The n ≤ 8 library is insufficient. Block composition with
small blocks cannot reach the interesting parameter regime.

---

### Experiment 5 — Forced Matching (`experiments/forced_matching/`)

**Question:** Can "α-forced" vertices (vertices that appear in every maximum
independent set) be used to systematically drop α via cross-edge wiring between
disjoint graph copies?

**Concept:** If vertex v is α-forced in G, then every max-IS uses v. Adding an
edge between an α-forced vertex in copy G₁ and an α-forced vertex in copy G₂
forces those two vertices to not coexist in any IS of G₁ ∪ G₂, dropping the
combined α by 1. Iterating this gives a construction recipe.

**What we found:**
- Hard floor at c = 0.9017 from |S| ≤ α and the discrete (n,α,d) options in
  the n ≤ 8 library.
- All large blocks tested — P(17), random n=10/12/16, Pareto-n24 — have
  **k* = 0 forced vertices**. No vertex appears in every max-IS.
- This is not accidental: graphs with α-forced vertices are structurally
  suboptimal. Good graphs are nearly vertex-transitive; every max-IS can
  avoid any single vertex.

**Conclusion:** Forced-matching doesn't scale. The mechanism is incompatible
with the structure of good graphs — you can only use it on graphs you don't
want.

---

### Experiment 6 — Pair-Forced Cross-Edges on P(17) (`experiments/pair_forced/`)

**Question:** Can we wire cross-edges between two disjoint P(17) copies to
drop α from 6 to 5, beating the trivial disjoint-union baseline?

**What we found:**
- 0 of 289 single cross-edges dropped α.
- Greedy multi-edge addition only raised c: 0.6789 → 0.8522 over 4 edges.
- The trivial disjoint union achieves c = 0.6789 (P(17)'s own ratio).
  Every cross-edge hurts.

**Why:** For a single edge (u₁, u₂) between copies to drop α, every max-IS
of the disjoint union must use *both* u₁ and u₂. But P(17) has no forced
vertices (k* = 0), so a max-IS avoiding u₁ always exists. One cross-edge
can never drop α.

**Conclusion:** Disjoint P(17) stacking gives c = 0.6789 for any N = 17k,
and no greedy wiring can improve it. This establishes the trivial baseline:
any construction worth considering needs to beat 0.679.

---

### Experiment 7 — Greedy Reachability (`experiments/reachability/`)

**Question:** Are SAT-optimal graphs reachable by greedy edge addition with
K₄-freeness checking? How sensitive is reconstruction to edge-ordering quality?

**What we found:**
- With a perfect oracle (knowing the exact target edge set), SAT-optimal graphs
  are fully reconstructible by greedy edge addition (monotone reachability).
- With noisy oracle: c degrades smoothly with noise level. Near-perfect ordering
  is needed at N ≥ 20.
- Greedy-optimal and SAT-optimal graphs are structurally distinct at N ≥ 20:
  same c_log is achievable in different graph classes.

**Conclusion:** SAT-optimal graphs are in principle reachable by greedy search,
but only with near-oracle edge ordering. This motivates learning a good priority
function (the FunSearch framing), rather than pure heuristic greedy.

---

### Experiment 8 — Selective Cross-Edges (`experiments/selective_crossedge/`)

**Question:** Can non-complete-bipartite cross-edges between blocks close the
IS-join gap? Depth ablation from 2-block compositions down to raw edges.

**Setup:** Three cross-edge strategies — random wiring, degree_balance
(connect low-degree to high-degree), alpha_stop (stop adding edges when α
would drop) — at N=16, 20, 24. Vary decomposition depth from 2 blocks
(IS-join) down to N individual vertices (equivalent to raw edge construction).

**What we found:**
- All three strategies plateau above c ≈ 0.87 at all sizes.
- Deeper decompositions (more, smaller blocks) are uniformly worse.
- alpha_stop is best but still ≈ 0.20 above SAT-optimal.

**Conclusion:** Neither block structure nor cross-edge strategy closes the gap.
The complete-bipartite IS-join seam was never the bottleneck — it's the block
decomposition framing itself that is incompatible with optimal structure.

---

### Experiment 9 — Baselines (`experiments/baselines/`)

**Question:** What is the attractor c_log for six heuristic construction
methods across N=6–20?

**What we found:**

| Method | Attractor c | Notes |
|---|---|---|
| Random + degree cap | 0.956 | Best heuristic |
| Regularity-aware | 0.990 | — |
| α-aware | 0.985 | — |
| c-minimize greedy | 0.990 | All three produce structurally identical graphs (Jaccard ≈ 1.0) |
| Block-join | 1.213 | Worst |
| Random block-join | 1.067 | — |

- All methods plateau strictly above 0.95 at scale.
- All strictly worse than P(17) at 0.679.
- The three "structured" methods (regularity, α-aware, c-minimize) converge
  to the same graphs — they're not meaningfully different.

**Conclusion:** Heuristic ceiling ≈ 0.95. Algebraic structure (Paley, Cayley)
or exact optimization (SAT) is needed to break below it.

---

### Evolutionary Search (`experiments/evo_search/`)

Best graphs found by an evolutionary construction loop at each size:

| N | Result |
|---|---|
| 30 | `best_N30.json` |
| 40 | `best_N40.json` |
| 50 | `best_N50.json` |
| 60 | `best_N60.json` |

These are the best K₄-free graphs the FunSearch evolutionary loop produced
at scale. They have not been ingested into `graph_db/` for comparison against
the algebraic and SAT results — that would be the natural next step.

---

## Overall Conclusions

**What works:**
- Greedy MIS as fast α proxy (ρ = 0.99 vs SAT)
- SAT evaluation is fast enough for any reasonable N (< 3 sec at N=80)
- Disjoint P(17) stacking gives c = 0.6789 trivially for N = 17k — this is the
  floor every construction must beat to be interesting

**What doesn't work:**
- Vertex-by-vertex construction (structural degree gradient, creates stars)
- IS-join / block decomposition (optimal graphs are non-compositional)
- Forced-matching (good graphs have no α-forced vertices by definition)
- Cross-edge wiring on P(17) (every edge hurts)
- Any pure heuristic method (hard ceiling ≈ 0.95)

**The gap:** Heuristic best ≈ 0.95. Trivial P(17) baseline = 0.679. SAT-certified
optima at small N = 0.67–0.74. This framework found no construction that beats
P(17) at scale.

**Remaining viable directions (not yet tried in this framework):**
- Raw edge construction with a learned algebraic priority function (closest to
  the original DeepMind cap-set FunSearch approach)
- LLM-in-the-loop on the raw `construct(N) → edge_list` interface — see
  `../OPENEVOLVE_ANALYSIS.md` and `../claude_search/`
