# Research Summary: FunSearch for the K₄-Free Independence Conjecture

## The Problem

The K₄-free independence conjecture asks: does every K₄-free graph on N vertices with max degree d have an independent set of size at least c·(N log d)/d for some constant c > 0? The best known bound (Shearer 1995) gives √(log d) instead of log d. We want to attack this computationally by finding graph construction algorithms that produce K₄-free graphs with small c = αd/(N log d) at N = 50-200, where exact optimization is infeasible.

---

## Theoretical Development

### What we built

We developed a formal framework connecting FunSearch-style program search to extremal graph theory, going through three rounds of postdoc review. The framework included:

1. **K₄-freeness reduction.** A graph is K₄-free iff every vertex's neighborhood is triangle-free. When constructing a graph by adding vertices or edges, this reduces K₄-checking to a cheap local test. This is the core enabling observation and the one result that survived everything.

2. **α-critical reduction.** Any graph minimizing c must be α-critical (every edge essential). This motivated searching over structured graph classes.

3. **IS-join composition theory.** Using Valencia-Leyva (2007), we formalized "independent-set joins" — composing two blocks by adding a complete bipartite graph between two independent sets. We proved: K₄-freeness is automatic (both connectors independent → all Proposition 4.1 conditions satisfied), and α(J) = α(G) + α(H) − 1 exactly at depth 1 (when α-dropping conditions are verified).

4. **Depth-1 exactness theorem.** The α formula is provably exact when composing two library blocks with verified α-dropping sets and maximality conditions.

5. **Depth-2 counterexample.** A postdoc constructed a concrete mechanism showing the α formula fails at depth 2+: independent sets route across blocks while avoiding connectors, causing arithmetic α to underestimate true α by Θ(depth).

6. **Iterative enrichment.** Compose at depth 1 → SAT verify → find fresh α-dropping sets → add to library → compose again. Each round doubles reachable N.

7. **β-parametrization.** Modeled d_min(N,α) ≈ (N/α)(log(N/α))^β. Shearer gives β ≥ 1/2, the conjecture is β = 1. Framed as a modeling ansatz, not a theorem.

### What two postdocs found wrong

- β is a "mixture parameter" not a structural invariant — different construction families may dominate different regimes
- Proposition 7.16 (α-dropping propagation) was false in general — replaced with depth-1-only guarantee
- The search objective is adversarially misaligned at depth 2+ (search rewards broken α computation)
- Credit assignment in vertex-by-vertex construction is essentially zero (no intermediate α signal)
- Compositional search might miss pseudorandom/algebraic extremizers entirely
- Failure of compositional search does not imply non-compositional extremizers

### What survived review

- K₄-freeness → triangle-free neighborhoods (confirmed correct and tight by all reviewers)
- α-critical reduction (Proposition 2.1, correct with minor phrasing fixes)
- IS-join K₄-freeness conditions (Proposition 4.1, "correct and tight" per reviewer)
- Depth-1 exactness (Theorem 7.16, proved and SAT-confirmed)

---

## Experiments Run

### Experiment 1: Vertex-by-Vertex Validation

**Setup:** 180 graphs at N=40, 60, 80 using four vertex-by-vertex priority functions (degree, inverse_degree, balanced, constant) and two random baselines (random edge, random edge with degree cap). SAT-computed exact α for all graphs.

**Key findings:**

| Finding | Result | Implication |
|---------|--------|-------------|
| SAT speed | < 3 sec at N=80, zero timeouts | SAT-in-loop is feasible; entire SAT-avoidance motivation was unnecessary |
| Greedy MIS correlation | ρ = 0.99 vs true α | Surrogate scoring works but isn't needed (SAT is fast enough) |
| Vertex-by-vertex quality | c = 2.9-17.6 | Catastrophically bad — produces degenerate star-like graphs |
| Random edge capped | c ≈ 1.1-1.2 | Beats all structured vertex-by-vertex methods by 2-3x |
| Signal existence | 10x spread in c across methods | Meaningful variance exists for optimization |

**Conclusion:** Vertex-by-vertex skeleton is not viable. Random edge addition is a strong baseline. SAT is not a bottleneck.

### Experiment 2: Block Composition (IS-Join)

**Setup:** Library of 83 K₄-free blocks (n ≤ 8) with 593 α-dropping independent sets. Exhaustive depth-1 IS-join composition (351,649 valid pairs, vectorized scoring in 5 min 41 sec). SAT verification on top candidates.

**Key findings:**

| N | Best c (blocks) | SAT-optimal | Gap |
|---|----------------|-------------|-----|
| 10 | 0.866 | ~0.77 | +12% |
| 13 | 0.888 | 0.773 | +15% |
| 16 | 0.902 | 0.721 | +25% |
| 21 | 0.888 | 0.733 | +21% |

- SAT verification: 10/10 exact α match (depth-1 guarantee confirmed)
- All compositions K₄-free verified
- Best blocks are small (4-6 vertices), regular, low degree
- Compositions are near-regular (degree sequence like [4,4,4,4,3,3,3,3,3,3])
- Iterative enrichment reached N=21 but saturated (α-dropping sets become rare)

**Conclusion:** Blocks produce better graphs than random edge construction (c ≈ 0.87 vs 1.2) but hit a ceiling ~15-25% above SAT-optimal.

### Experiment 3: Edge Trimming

**Setup:** Took top 50 IS-join compositions, stripped redundant edges (every edge checked: remove it, SAT α, keep if α increased). Also checked whether SAT-optimal N=16 graphs decompose as IS-joins.

**Key findings:**

| Finding | Result |
|---------|--------|
| Trimming improvement | 0-7% (only helped at N=21 where d_max dropped from 5→4) |
| α-critical + α-dropping | Fundamentally incompatible: trimmed graphs have zero α-dropping sets |
| SAT-optimal decomposition | N=16 optimal graphs have ZERO valid IS-join decompositions across all 2^16 partitions |
| Enrichment with trimmed blocks | Impossible (no α-dropping sets exist) |

**Conclusion:** The IS-join structure itself is the bottleneck, not edge count. Optimal graphs are structurally non-compositional (no bipartite seam). Trimming cannot fix a topological constraint. The iterative enrichment pipeline is broken at a fundamental level: compose → trim → compose is impossible.

---

## What We Threw Away

### Entire theoretical framework (Sections 2-7 of manuscript)

- α-critical reduction (Proposition 2.1): correct but not operationally used
- Hajnal's theorem: provides degree upper bound, never used in algorithm
- Valencia-Leyva 1-join theory: the IS-join ceiling makes this irrelevant
- α-dropping independent sets: incompatible with α-criticality
- Depth-1 exactness theorem: correct but unnecessary (SAT is fast)
- Depth-2 counterexample: important for understanding, but moot since we're not using depth-2
- Mixed joins: never reached implementation
- Iterative enrichment: broken by α-critical/α-dropping incompatibility
- β-parametrization: too unstable to estimate from data

### Approaches that failed

- Vertex-by-vertex construction with any priority function
- IS-join with complete bipartite cross-edges
- Edge trimming as a way to close the IS-join gap
- Iterative enrichment beyond round 1
- Avoiding SAT (turned out to be unnecessary)

---

## What Survived

### One theorem

**K₄-freeness reduces to triangle-free neighborhood checking.** When adding an edge (i,j), check that the common neighborhood of i and j contains no edge. O(d²), local, no global checking needed. This is the skeleton's constraint enforcement, analogous to `can_be_added` in FunSearch for cap sets.

### Three empirical facts

1. **SAT is fast.** Under 3 seconds at N=80. Can be in the inner loop.
2. **Greedy MIS works as a proxy.** ρ = 0.99 correlation with true α. Available if SAT ever becomes too slow at larger N.
3. **Block composition produces c ≈ 0.85-0.90.** Better than random, worse than optimal. Useful as a starting point.

### One architectural insight

**Blocks provide a scaffold that factorizes the search problem.** Pre-fix two half-graphs from a library. FunSearch learns only which cross-edges to add. This separates the macro decision (which blocks, implicitly setting rough α and d) from the micro decision (which specific connections). No IS-join constraint — arbitrary cross-edges, SAT for scoring.

---

## Two Viable Paths Forward (Both Untested)

### Path A: Blocks with selective cross-edges

Take two blocks from the library. FunSearch evolves `cross_edge_priority(v_a, v_b, features)`. Skeleton adds cross-edges greedily with K₄-free check. SAT scores. Sweep over block pairs externally.

**Pros:** Smaller search space (64 cross-edges for 8+8 blocks vs 120 total edges), implicit degree budgeting, avoids PatternBoost's failure mode (flat landscape on raw graphs), blocks provide feature-rich vertex identities.

**Cons:** Still constrains the search to respect a two-block partition. SAT-optimal graph doesn't have this partition structure (confirmed at N=16).

### Path B: Raw edge construction with algebraic labeling

Label N vertices as elements of Z_p. FunSearch evolves `priority(i, j, N)` where i, j are algebraic identities. Skeleton adds edges greedily with K₄-free check and degree cap. SAT scores. Sweep d_cap externally.

**Pros:** Maximum expressiveness, can reach any K₄-free graph, algebraic labeling enables discovery of Paley-like constructions. Closest analog to FunSearch on cap sets.

**Cons:** PatternBoost already failed on similar raw-graph optimization. d_cap sweep is expensive. Dual objective (α vs d) may be hard to balance even with d_cap.

### What would decide between them

Run both on N=16-30. If either produces c < 0.80 (within 10% of SAT-optimal), that's the path. If both plateau above 0.85, the problem may be fundamentally harder than what FunSearch-style search can handle, and the construction approach needs rethinking.

---

## Compute Used

| Experiment | Wall time | Graphs generated | SAT calls |
|-----------|-----------|-----------------|-----------|
| Exp 1 (validation) | ~5 min | 180 | 180 |
| Exp 2 (block composition) | ~6 min | 351,649 scored, 10 SAT-verified | 10 |
| Exp 3 (trimming) | ~13 min | 50 trimmed | ~3,000 (50 graphs × ~60 edges each) |
| Library construction | running (7+ hr est.) | 5,603 blocks | ~50,000+ |

---

## Documents Produced

1. **Technical manuscript** (funsearch-k4-writeup): Full formal framework with proofs, went through 3 rounds of postdoc review. Sections 2-7 are now mostly historical — the theoretical infrastructure for a path we're no longer taking. Section 1 (problem statement), Section 4 Corollary 4.3 (K₄-free reduction), and Section 8 (limitations) remain relevant.

2. **Surrogate comparison document** (surrogate-comparison): Analysis of exact vs proxy scoring philosophies. Key conclusion: SAT is fast enough that surrogates aren't needed, but greedy MIS (ρ=0.99) is available as fallback.

3. **Colleague summary** (colleague-summary): Non-technical overview suitable for collaborators.

4. **Validation experiment design** (validation-experiment): Pre-FunSearch experiment plan with code, SAT encoding, analysis plan.

5. **Experiment prompts** for Claude Code: Environment setup, block decomposition, enrichment, trimming.