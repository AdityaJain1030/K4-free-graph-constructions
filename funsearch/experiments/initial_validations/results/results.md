This data is extremely informative. Let me walk through what it tells us.

## The Good News

**SAT is trivially fast.** Max 2.88 seconds at N=60, max 2.54 seconds at N=80. Mean times under 0.4 seconds at all sizes. Zero timeouts. SAT is not a bottleneck at all — you could put it in a tight inner loop at these sizes and run thousands of evaluations per hour. This kills the entire debate about surrogates vs exact scoring. Just use SAT.

**Greedy MIS is an excellent proxy.** Spearman ρ = 0.99 against true α at all N values. If you ever need a pre-filter for larger N, greedy MIS works. Caro-Wei is mediocre (ρ = 0.58) — it's a degree-based bound that doesn't capture global independence structure.

## The Bad News

**The vertex-by-vertex skeleton is catastrophically bad.** Look at the c values:

| Method | N=40 | N=60 | N=80 | 
|--------|------|------|------|
| degree | 10.1 | 14.0 | 17.6 |
| balanced | 10.1 | 14.0 | 17.6 |
| inverse_degree | 2.87 | 3.61 | 4.57 |
| random (v-by-v) | 3.22 | 4.21 | 5.10 |
| random_edge | 1.51 | 1.54 | 1.56 |
| random_edge_capped | 1.16 | 1.20 | 1.22 |

The `degree` and `balanced` methods produce degenerate star graphs — d_max equals N−1, meaning one vertex connects to literally every other vertex. With only 77 edges at N=40 (average degree ≈ 3.85), the graph is a star with a few extra edges. α = N−2 because almost all vertices are isolated from each other. These are the worst possible K₄-free graphs for our purpose. And they're deterministic — zero variance across seeds.

`inverse_degree` is better but still produces heavily unbalanced graphs with d_max = 54 at N=80 (67% of N) and c values that are **increasing with N** — the wrong direction.

**Random edge addition beats every vertex-by-vertex method by a factor of 2-3x.** The best vertex-by-vertex (inverse_degree at N=40) gives c = 2.87. Random edge gives c = 1.34. Random edge capped gives c = 1.09. The gap is enormous and no priority function is going to close it.

## Why Vertex-by-Vertex Fails

The problem is structural. When you add vertices sequentially, early vertices accumulate connections from many later vertices (they're "available" as neighbors for a long time), creating a degree gradient. Vertex 0 might end up with degree 30+ while vertex 39 has degree 3. This inflates d_max, which inflates c directly.

The data confirms this: vertex-by-vertex methods all have d_max much larger than d_avg. At N=80, inverse_degree has 2133 edges (d_avg = 53.3) and d_max = 54 — nearly regular, but at a very high degree. The random_edge_capped method has 717 edges (d_avg = 17.9) and d_max = 18 — also near-regular, but at a much lower degree with comparable α.

The vertex-by-vertex skeleton maximizes edges because it adds every neighbor that passes the triangle-free check. It produces the densest K₄-free graph consistent with the vertex ordering. That's exactly the wrong objective — we want the sparsest graph that still has small α.

## What Actually Works

`random_edge_capped` is the clear winner:
- c ≈ 1.09–1.25, roughly flat across N=40-80
- d_max = 12-18 (well controlled)
- α = 9-16
- Near-regular degree distribution

This is an edge-addition process with a degree cap — add random edges that maintain K₄-freeness, but skip edges where either endpoint has already reached the target degree. It's close to what we discussed as "Fix C" (fix target degree, build within that constraint).

## What This Means for FunSearch

**The vertex-by-vertex skeleton as designed is not viable.** FunSearch would need to evolve a priority function that overcomes a 2-3x gap relative to a random baseline. That's not what FunSearch is designed to do — it makes incremental improvements to an already-reasonable baseline, not miracles from a broken starting point.

**Two paths forward:**

**Path 1: Edge-centric FunSearch.** Redesign the skeleton around edge addition, not vertex addition. The LLM evolves a priority function over edges — `priority(i, j, graph_state, N)` — and the skeleton greedily adds edges in priority order, checking K₄-freeness and degree cap at each step. The `random_edge_capped` method becomes the trivial baseline (priority = random), and FunSearch tries to find priority functions that beat random edge selection. The K₄-freeness check is still O(d²) per edge.

**Path 2: Block composition.** The block approach avoids the vertex-ordering problem entirely. You're choosing which pre-built blocks to combine, not which vertices to connect. The c values from block composition would depend entirely on the library contents, not on a sequential construction bias. And the depth-1 arithmetic gives you exact α for free.

Given this data, I'd actually say Path 2 (blocks) got significantly more attractive. The vertex-by-vertex failure isn't about naive priority functions — it's a structural bias of the sequential construction. Blocks don't have that bias. The question is whether the block search space can achieve c ≈ 1.0-1.2 (matching random_edge_capped). That's Experiment 2 — the block decomposition check.

**Immediate next step:** Run Experiment 2. Build the library, do exhaustive depth-1 composition, see what c values you get. If blocks can match random_edge_capped (c ≈ 1.2), you have a viable FunSearch skeleton with exact scoring and no sequential bias. If they can't, Path 1 (edge-centric) is the fallback.