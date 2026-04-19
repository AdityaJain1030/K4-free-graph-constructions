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

---

## Addendum (2026-04-16 evening): Forced-Matching, Pair-Forced, Baselines

Three follow-up experiments were run after the main document was written.

### Forced-matching construction (`experiments/forced_matching/`)

Attempted to improve c by "forcing" α to drop through specific cross-matchings between library blocks. All sweeps hit a hard asymptotic floor at **c = 0.9017** driven by the structural inequality `|S| ≤ α` together with the best (n, α, d) ratio attainable from the n ≤ 8 library. Extension to large blocks (Paley P(17), random K₄-free at n=10/12/16, pareto-n24) gave **k* = 0 for all 5 blocks** — no α-forced vertices exist in any of them. The construction simply cannot be used with large K₄-free blocks.

### Pair-forced cross-edges on P(17) (`experiments/pair_forced/`)

Tested whether any single cross-edge between two disjoint copies of P(17) drops α (from 6 to 5). Result: **0/289 cross-edges drop α.** Row uniformity confirms this is a vertex-transitivity consequence, not a sampling artifact. Greedy multi-edge wiring only makes c worse (0.6789 → 0.8522 over 4 edges, hitting d_cap=12).

### Attractor observation: disjoint unions of P(17) give c = 0.6789

The "best c = 0.6789" in the pair_forced trajectory is the **initial** state — two disjoint copies of P(17) before any cross-edges. This comes from P(17)'s own ratio: α/n · d/log(d) = 3/17 · 8/ln(8) = 0.6789. Disjoint unions preserve the ratio, so **for every N divisible by 17, c ≤ 0.6789 is achievable trivially** with no cross-edges. This is below every heuristic construction's attractor (baselines cluster at c ≈ 0.95–1.20) and below the reliable portion of the ILP Pareto frontier. The takeaway: no construction that produces c > 0.68 is actually novel above this trivial baseline — it's strictly worse than stacking P(17).

### Baselines sweep (`experiments/baselines/`)

Six heuristic methods (random, block-join, regularity-aware, α-aware, c-minimize) run for N=6..20 with d_cap sweep. Attractor values (mean of last 20 c samples):

| method | attractor c |
|--------|-------------|
| method1 (random+d_cap) | 0.956 |
| method2 (block join) | 1.213 |
| method2r (random block join) | 1.067 |
| method3 (regularity) | 0.990 |
| method3b (α-aware) | 0.985 |
| method4 (c-minimize) | 0.990 |

All methods plateau **above 0.95**, all methods are **strictly worse than P(17) disjoint unions (0.679)**. Methods 3/3b/4 produce identical or near-identical graphs (Jaccard ≈ 1.0), so they are effectively duplicates.

### SAT-optimal reference is unreliable for N ≥ 26

The ILP Pareto frontier in `SAT_old/pareto_reference/pareto_n*.json` used time-limited solves (600s–1800s). Anomalies: N=25 gives c=0.72 (α=5, d=7) but N=26 gives c=0.93 (α=5, d=12); N=32+ gives c > 1.55 which is worse than random. Treat these as incomplete upper bounds, not proven optima.

### Paley family sweep — P(17) is the ceiling

Tested P(q) for all primes q ≡ 1 mod 4 up to q ≤ 61:

| q | n | d | α | K4-free | c |
|---|---|---|---|---------|---|
| 5 | 5 | 2 | 2 | ✓ | 1.154 |
| 13 | 13 | 6 | 3 | ✓ | 0.773 |
| **17** | **17** | **8** | **3** | **✓** | **0.679** |
| 29 | 29 | 14 | 4 | ✗ | (0.732) |
| 37 | 37 | 18 | 4 | ✗ | (0.673) |
| 41 | 41 | 20 | 5 | ✗ | (0.814) |
| 53 | 53 | 26 | 5 | ✗ | (0.753) |
| 61 | 61 | 30 | 5 | ✗ | (0.723) |

P(29) onwards contains K4 (ω ≥ 4). So **P(17) is the largest K4-free Paley graph**, and within this family, disjoint unions of P(17) are the minimum-c construction.

### Revised verdict on paths A and B

The c < 0.80 threshold from the original document is **already met by the trivial baseline** of stacking P(17). What we still lack is a construction producing c < 0.679 at large N — nothing tested so far does that. The ambitious goal should be restated as "beat 0.679" not "beat 0.80."

Two directions considered:
1. **K4-free subgraphs of P(37)** — *tested, negative.* Greedy K4-removal on P(37) over 20 random seeds removes ~80 edges, leaves d_max=16..18, but α jumps from 4 to 8..9, giving c ≈ 1.25 (well worse than P(17) at 0.68). Intuition: removing edges raises α proportionally more than it lowers d. Greedy edge-removal is not viable.
2. **Cayley graphs on Z_p with non-QR connection sets** — not tested, remains open. Other algebraic connection sets might produce K₄-free graphs with better (α, d) ratios than Paley gives.