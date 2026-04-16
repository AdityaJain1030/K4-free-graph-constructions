# FunSearch for the K₄-Free Independence Conjecture

## The Problem

There's a longstanding open conjecture: every K₄-free graph on N vertices with max degree d has an independent set of size at least c · (N log d)/d for some universal constant c > 0. The best proved bound (Shearer 1995) is weaker — it gives √(log d) instead of log d. Nobody has improved this in 30 years.

We want to attack this computationally. The strategy: search for K₄-free graph *construction algorithms* that produce graphs with small c = αd/(N log d) at large N. If we find families where c stays bounded away from zero as N grows, that's evidence for the conjecture. If we find families where c trends to zero, that's evidence against.

The catch: computing the independence number α is NP-hard (requires SAT), and the interesting regime is N = 50–200 where exact optimization is infeasible. We need a way to search intelligently at scale.

## Why FunSearch Fits

FunSearch (Romera-Paredes et al., Nature 2024) evolves *programs* that construct solutions, rather than searching for solutions directly. It pairs an LLM with an evaluator: the LLM proposes construction algorithms, the evaluator scores them, and an evolutionary loop improves the algorithms over time.

For cap sets (their main result), the setup was: evolve a priority function that ranks vectors in Z₃ⁿ, then greedily build a cap set by adding vectors in priority order, checking validity at each step. The validity check was cheap and local. The LLM only needed to learn one thing — a good priority function.

We can do the same thing for K₄-free graphs.

## The Skeleton: K₄-Free for Free

The key observation: a graph is K₄-free if and only if every vertex's neighborhood is triangle-free. So when adding a new vertex v with neighborhood S, we just check that G[S] contains no triangle. If it doesn't, the resulting graph is K₄-free. This check is O(d²) — fast and local.

This gives us a FunSearch skeleton:

```
for each new vertex k:
    score every existing vertex v using priority(v, k, graph_state, N)
    greedily add v's neighbors in priority order,
        skipping any that would create a triangle in the neighborhood
    stop when target degree is reached
```

The triangle-free check guarantees K₄-freeness for ANY priority function. The LLM's only job is to learn a good priority function. The skeleton handles the hard constraint automatically, exactly like `can_be_added` in the cap set skeleton.

## The Scoring Problem

Here's where it gets harder than cap sets. In cap sets, the score is the size of the cap set — one number, always improving, cheap to compute. For us, the score is c = αd/(N log d), which requires computing α. That's a SAT call.

Three approaches:

**Exact scoring (SAT).** Compute true α after building the graph. Correct but expensive — SAT at N=80 might take minutes. Limits throughput to ~10² evaluations. May not be enough for FunSearch's evolutionary loop to work.

**Surrogate scoring.** Replace α with cheap proxies: Caro-Wei bound (α ≥ Σ 1/(d(v)+1)), greedy MIS (run random greedy 20 times, take the max), or an ensemble. These are O(N²) — throughput of 10⁵+ evaluations. But they might not rank candidates correctly. If the proxy doesn't correlate with true α, the search optimizes an illusion.

**Hybrid.** Use surrogates to filter candidates fast (discard obviously bad ones), then SAT-verify only the survivors. Gets most of the throughput benefit with correctness on the candidates that matter.

Which one works depends on empirical facts we don't have yet — specifically, how well cheap proxies correlate with true α for K₄-free graphs at N=40-80. The validation experiment (below) answers this.

## The Dual Objective Problem

In cap sets, bigger is always better — one objective. Here we're balancing two things: small α (few independent vertices) and small d (sparse graph). Minimizing c requires both simultaneously, and they push in opposite directions — adding edges suppresses α but increases d.

The vertex-by-vertex approach has no natural way to handle this. You could fix a target degree d* and optimize only α, but this introduces its own problems: you don't know what d* to target (the optimal degree depends on N and α in ways we're trying to discover), the triangle-free constraint may prevent reaching d* for some vertices, and you still have the credit assignment problem — no intermediate feedback on α during construction.

This is one of the main motivations for the block decomposition approach, which handles the dual objective far more naturally (see below).

## Motivation for Block Decomposition

The vertex-by-vertex approach has two weaknesses. First, no intermediate feedback on α during construction — adding vertex k with some neighborhood S, you have no idea whether this helped or hurt α until the entire N-vertex graph is built and scored. This is a severe credit assignment problem. Second, the dual objective: the LLM must simultaneously learn to suppress α while controlling degree, with no way to separate these concerns.

Block decomposition addresses both problems simultaneously. A graph is α-critical if removing any edge increases α — meaning every edge is essential. Any graph minimizing c must be α-critical (if an edge were removable, removing it would lower d without changing α, improving c). Valencia and Leyva (2007) showed that α-critical graphs can be decomposed via "1-joins" — a way of composing two graphs where the independence number of the result is exactly α(G) + α(H) − 1, computable arithmetically with no SAT call. The degree structure is also fully determined: interior vertices keep their original degree, connector vertices gain a known number of new neighbors.

This means that if you pre-build a library of small K₄-free blocks with known α values, composing two blocks gives you an *instant, exact score* for the resulting graph. There is no dual objective — c is a deterministic function of the block choice and connector choice. There is no credit assignment problem — each composition decision has an immediate score. The LLM's task reduces to discrete optimization: which pair of blocks and which connectors give the best c?

The catch: this arithmetic α formula is only provably correct for depth-1 compositions (combining two library blocks directly). At depth 2+, maximum independent sets can span across multiple blocks in ways the formula doesn't capture, and the computed α drifts from reality — a concrete counterexample mechanism shows the gap grows linearly with composition depth. However, this depth limit is not a hard ceiling: the best depth-1 compositions can be SAT-verified, equipped with fresh α-dropping sets, and added back to the library as new first-class blocks. Each round of this iterative enrichment roughly doubles the reachable N while maintaining exact scoring, with the only bottleneck being SAT feasibility at the verification step (~20 SAT calls per round on the top candidates).

The interesting open question: do the optimal K₄-free graphs we've found via SAT at small N (≤22) actually decompose as 1-joins of smaller blocks? If yes, the block approach is searching in the right space and is arguably the superior FunSearch formulation for this problem. If no, we fall back to vertex-by-vertex with surrogate scoring — messier but more expressive. This is testable with a small experiment.

## Validation Experiments (Pre-FunSearch)

Before building the full FunSearch pipeline, two cheap experiments tell us whether to proceed:

**Experiment 1: Vertex-by-vertex feasibility.** Build ~120 graphs at N=40, 60, 80 using simple hand-designed priority functions and random baselines. Compute exact α via SAT for all of them. This tells us: (a) is SAT fast enough at these sizes? (b) is there meaningful variance in c across methods? (c) do structured priority functions beat random? If SAT is feasible and there's signal, FunSearch is worth trying. Also compute cheap proxies (Caro-Wei, greedy MIS) on the same graphs and measure rank correlation with true c — this tells us whether surrogate scoring works.

**Experiment 2: Block decomposition check.** Build a library of small K₄-free α-critical blocks (up to ~12 vertices). Exhaustively compose all valid pairs. Compare the resulting graphs against SAT-optimal graphs at N=12-22. Check if any SAT-optimal graph literally decomposes as a 1-join of two library blocks. Also check if Paley graphs decompose. This tells us whether compositionality is a real feature of optimal graphs or just a theoretical convenience.

Both experiments cost about a day of coding and a few hours of compute each. They produce concrete go/no-go signals for the full FunSearch effort.

## Summary

| Component | Status |
|-----------|--------|
| K₄-free enforcement | Solved — triangle-free neighborhood check |
| FunSearch skeleton | Two options: vertex-by-vertex or block composition |
| Scoring | Three options (SAT / surrogate / hybrid); validation experiment decides |
| Dual objective (α vs d) | Solved by block approach (instant exact c); open for vertex-by-vertex |
| Credit assignment | Solved by block approach (immediate score per step); open for vertex-by-vertex |
| Block decomposition | Depth-1 exact, theoretically motivated, needs empirical validation |
| Vertex-by-vertex | Full expressiveness, but delayed reward and dual objective issues |
| Priority function design | Open — what FunSearch evolves (in either approach) |
| Vertex ordering | Solvable — structural features or algebraic labeling |