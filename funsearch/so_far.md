# Computational Approaches to the K₄-Free Independence Number Conjecture

## 1. The Conjecture

For every K₄-free graph G on N vertices with maximum degree d, does there exist a universal constant c > 0 such that:

$$\alpha(G) \geq c \cdot \frac{N \log d}{d}$$

The best known bound (Shearer 1995) gives α(G) ≥ c₁ · (N/d)√(log d) — a √(log d) factor instead of the conjectured log d. This has stood for 30 years.

We define c(G) = α(G)·d_max/(N·log d_max) as the quantity to minimize. If inf c(G) > 0 across all K₄-free graphs as N → ∞, the conjecture is true. If it trends to zero, the conjecture is false.

---

## 2. Prior Computational Work

### 2.1. SAT-optimal search (N ≤ 22)

We ran exact optimization via SAT solvers, finding the K₄-free graphs minimizing c at each N from 12 to 22. All verified optimal.

| N | d | α | c |
|---|---|---|---|
| 12 | 5 | 3 | 0.777 |
| 14 | 6 | 3 | 0.718 |
| 16 | 8 | 3 | 0.721 |
| 18 | 6 | 4 | 0.744 |
| 20 | 7 | 4 | 0.719 |
| 22 | 9 | 4 | 0.745 |

Key observations: c fluctuates around 0.72 and does not trend toward zero, consistent with the conjecture. All optimal graphs are regular. The α values match Ramsey predictions at most sizes.

### 2.2. The N=24 counterexample

At N=24, the optimal graph has α=6, d=4 (c ≈ 0.721), beating the Ramsey-predicted α=4, d=10 (c ≈ 0.724). The sparser graph with larger α wins because d/log(d) drops faster than α rises. This kills the hypothesis that optimal α is always the Ramsey minimum.

### 2.3. Near-regular SAT search (N ≤ 30)

Enforcing near-regularity (motivated by all SAT-optimal graphs being regular) and searching via SAT produced good results up to N≈30 with c in the 0.7-0.8 range. Beyond N=30, the SAT solver times out — finding the optimal graph is computationally infeasible, not just evaluating a given graph.

### 2.4. PatternBoost/axplorer (failed)

We attempted to use axplorer (an implementation of DeepMind's PatternBoost) to optimize c directly and to minimize α at fixed N. Both failed beyond R(4,4). The core difficulty: computing α is NP-hard and PatternBoost could not learn to balance α and d simultaneously. The optimization landscape is flat — most local changes to a graph barely affect α.

### 2.5. Paley graph perturbations (failed)

Paley graphs (Cayley graphs over F_q using quadratic residues) are among the best known Ramsey graph constructions. We tried perturbing Paley graphs to make them K₄-free for N > 17. Results were terrible — small perturbations catastrophically increased α. This suggests optimal K₄-free graphs sit on fragile algebraic ridges, not smooth optimization basins.

### 2.6. Sandwich bounds

The feasible (N, α, d) triples are constrained:

- **Shearer lower bound:** d ≥ (c₁N/α)√(log(N/α))
- **Caro-Wei lower bound:** d ≥ N/α − 1
- **Neighborhood Ramsey upper bound:** d ≤ R(3, α+1) − 1 (since neighborhoods in K₄-free graphs are triangle-free)

At each N, only a few α values are feasible, and d lives in a narrow range for each α. As N grows, the lower bound rises until it collides with the Ramsey ceiling — this collision defines the Ramsey number R(4, α+1). The N values where the bounds are tightest are where the conjecture is most constrained and where computational search should focus.

---

## 3. Attempting FunSearch: The Theoretical Framework

### 3.1. Why FunSearch

FunSearch (Romera-Paredes et al., Nature 2024) evolves construction *programs* using an LLM + evaluator loop. It succeeded on cap sets by: (1) enforcing the constraint cheaply (validity check per element), (2) having a skeleton that handles constraint enforcement, (3) the LLM learns only a priority function. We wanted to apply the same paradigm to K₄-free graphs.

### 3.2. The K₄-freeness reduction (survives)

The key enabling observation: G is K₄-free if and only if every vertex's neighborhood is triangle-free. When adding an edge (i,j), we check that the common neighborhood of i and j contains no edges. This is O(d²), local, and analogous to `can_be_added` in the cap set FunSearch skeleton. This is the one theoretical result that survived the entire research process.

### 3.3. α-critical theory and IS-join composition (discarded)

We developed a framework based on Valencia-Leyva (2007) to avoid SAT calls via algebraic α computation:

- **α-critical reduction:** optimal graphs must be α-critical (every edge essential). Correct, proved, but not operationally useful.
- **IS-join composition:** compose two blocks by adding complete bipartite edges between two "α-dropping" independent sets. Gives α(J) = α(G) + α(H) − 1 exactly at depth 1 (proved, SAT-verified 10/10).
- **Iterative enrichment:** compose → SAT verify → find new α-dropping sets → add to library → compose again. Each round doubles reachable N.

This went through three rounds of postdoc review, producing a formal manuscript with full proofs.

### 3.4. What the postdocs found

**Depth-2 counterexample:** A postdoc constructed a concrete mechanism showing the α formula breaks at depth 2+. Independent sets can route across multiple blocks while avoiding inherited connectors. The gap grows as Θ(depth). This killed deep composition.

**α-critical and α-dropping are incompatible:** In an α-critical graph, every edge is essential, so removing any independent set can only increase α — never decrease it. This means trimmed (α-critical) graphs have zero α-dropping sets and cannot be used for further composition. The iterative enrichment pipeline is fundamentally broken.

**Objective misalignment:** At depth 2+, the search actively rewards candidates where the α computation is most broken (since underestimated α gives artificially good c scores).

**Structural limitations:** The search space of IS-join-decomposable graphs may exclude the true extremizers, which could be pseudorandom or algebraic (Paley-type) in nature. Failure of the compositional search does not imply extremizers are non-compositional — only that the specific compositional class is too restricted.

---

## 4. Experimental Results (Today)

### 4.1. Experiment 1: Vertex-by-vertex validation (180 graphs, N=40-80)

**SAT evaluation is trivially fast.** Mean < 0.4 seconds, max 2.88 seconds at N=80. Zero timeouts. Computing α of a *given* graph is completely feasible in an inner loop. This is the distinction from SAT *optimization* (which times out at N=30): evaluation is fast, optimization is hard. This single finding killed the entire motivation for the IS-join framework — all that theory was built to avoid SAT calls that take 3 seconds.

**Greedy MIS is a near-perfect α proxy.** Spearman ρ = 0.99 against true α at all N. Caro-Wei is weak (ρ = 0.52). If SAT ever becomes too slow at larger N, greedy MIS is available.

**Vertex-by-vertex construction is catastrophically bad.** The "degree" and "balanced" priority functions produce degenerate star-like graphs with d_max = N−1 and c > 10. Even "inverse_degree" (the best structured method) gives c ≈ 2.9-4.6, increasing with N. The sequential vertex-addition structure creates inherent degree gradients — early vertices accumulate connections from many later vertices. No priority function can fix this.

**Random edge addition with a degree cap beats everything.** c ≈ 1.1-1.2 at N=40-80, roughly flat. This is a graph that adds random K₄-free edges until vertices reach a target degree. It has no learned structure at all — it's the trivial baseline.

### 4.2. Experiment 2: Block composition via IS-join (351,649 compositions)

**Library:** 83 K₄-free blocks (n ≤ 8) with 593 α-dropping independent sets. Enumerated via nauty, α computed via SAT.

**Composition:** All valid IS-join pairs scored via vectorized numpy computation (6.2B operations in 5 min 41s — 60x speedup over naive Python).

**Results:**

| N | Best c (blocks) | SAT-optimal | Gap |
|---|----------------|-------------|-----|
| 10 | 0.866 | ~0.77 | +12% |
| 13 | 0.888 | 0.773 | +15% |
| 16 | 0.902 | 0.721 | +25% |
| 21 | 0.888 | 0.733 | +21% |

SAT verification: 10/10 exact α match. Zero K₄ violations. The depth-1 guarantee works perfectly.

Block composition beats random edge construction (c ≈ 0.87 vs 1.2) but hits a ceiling 15-25% above SAT-optimal.

### 4.3. Experiment 3: Edge trimming and decomposition analysis (50 graphs)

**Trimming barely helps.** Removing redundant edges from IS-join compositions improved c by 0-7%. At N=10-16, d_max was already minimal at 4 so trimming couldn't reduce it. Only at N=21 did trimming reduce d_max from 5 to 4, giving a modest improvement (0.888 → 0.824).

**SAT-optimal graphs are NOT IS-join-decomposable.** The N=16 SAT-optimal graph (α=4, d=4, c=0.721) has zero valid IS-join decompositions across all 2^16 possible vertex partitions. Both Pareto-optimal entries at N=16 fail this check. Only degenerate/sparse entries decompose trivially.

**The IS-join bipartite constraint is the fundamental bottleneck.** The IS-join forces a complete bipartite cross-connection between connector sets. This creates a structural "seam" that optimal graphs don't have. This cannot be fixed by trimming — trimming removes edges but cannot add edges between non-connector vertices.

---

## 5. What Survived

### One theorem

K₄-freeness ↔ triangle-free neighborhoods. When adding edge (i,j), check that common neighbors of i and j contain no mutual edge. O(d²), local, sound.

### Key empirical findings

1. SAT evaluation is fast (< 3s at N=80); SAT optimization times out at N>30
2. Greedy MIS gives ρ = 0.99 correlation with true α
3. Optimal graphs at N ≤ 22 are regular with c ≈ 0.72
4. The N=24 counterexample kills α-Ramsey-minimum as a general rule
5. Paley perturbations collapse — algebraic structure is fragile
6. IS-join is structurally incompatible with optimal graphs
7. α-critical and α-dropping are fundamentally incompatible
8. Vertex-by-vertex construction is degenerate; edge-based construction is the correct primitive
9. Near-regular SAT search achieved c ≈ 0.7-0.8 up to N=30, the best results to date

---

## 6. Open Paths

### Path A: Blocks with selective cross-edges

Two library blocks, FunSearch evolves arbitrary (non-bipartite) cross-edge selection, K₄-free skeleton, SAT scoring. Blocks provide scaffold and implicit degree budgeting. Sweep block pairs externally. Untested.

### Path B: Raw edge construction with algebraic labeling

Vertices labeled as elements of Z_p. FunSearch evolves priority(i, j, N). Skeleton adds edges greedily with K₄-free check. SAT scoring. Most expressive option, closest to cap-set FunSearch. But PatternBoost failed on a similar setup. Untested with FunSearch specifically.

### Path C: Identifying critical N values

Use the sandwich bounds (Shearer + Ramsey ceiling) to identify N values where the feasibility region is tightest. These are where counterexamples are most likely and where computation should focus. Does not require ML — this is analytic work that guides all other approaches.

### The deciding experiment

Run Path A and Path B on N=16-30 where we have SAT-optimal baselines. If either produces c < 0.80 (within 10% of known optima), that's the path. If both plateau above 0.85, the FunSearch approach may need fundamentally different structural input.

---

## 7. Lessons Learned

**Don't theorize to avoid computation you haven't benchmarked.** We built weeks of theory to avoid SAT calls that take 3 seconds. The very first experiment killed the motivation.

**Test baselines before building infrastructure.** Random edge addition with a degree cap (c ≈ 1.2) should have been the first thing we computed. It would have immediately shown that vertex-by-vertex is broken and set the bar for blocks.

**Structural impossibilities are more valuable than near-misses.** The finding that SAT-optimal graphs don't IS-join-decompose, and that α-critical graphs can't have α-dropping sets, are clean negative results that permanently close off entire research directions. They're worth more than an approach that gets c = 0.88 instead of 0.72.

**The simplest framing is usually right.** The surviving contribution is one observation: K₄-free ↔ triangle-free neighborhoods. One line of math, O(d²) per edge, handles the hardest constraint. Everything else was scaffolding.