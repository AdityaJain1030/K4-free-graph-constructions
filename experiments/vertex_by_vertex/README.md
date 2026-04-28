# Vertex-by-Vertex Construction

## Why We Did This

The most natural way to build a K₄-free graph incrementally is to add one
vertex at a time: for each new vertex, wire it to some subset of existing
vertices while checking that no K₄ is created. The appeal is that the K₄
constraint stays cheap to enforce locally (O(d²) per edge), and you can
apply any priority function — degree, random, neighborhood overlap — to
guide which edges to add.

This experiment measures whether any priority function can produce competitive
graphs, how bad c_log gets in practice, and what structural property breaks it.

## The Problem

Vertex-by-vertex construction has a fundamental degree-gradient problem.
Early vertices accumulate edges from every subsequent vertex that connects to
them. Late vertices are constrained by an already-dense neighborhood and
can only add a few edges. The result is a highly skewed degree sequence:
a small core of very high-degree vertices surrounded by low-degree leaves.

`c_log = α · d_max / (N · ln(d_max))` is punished doubly:
- `d_max` is inflated by the early-vertex hub
- `α` is inflated because the low-degree leaves are easy to include in a
  large independent set (the hub and its neighbors are few)

Both effects push c_log up, far above the P(17) benchmark of 0.679.

## What This Experiment Measures

For each construction method × graph size pair, we build K₄-free graphs and
record:
- `c_log`: the primary metric
- degree sequence statistics (max, mean, std, gini coefficient)
- how degree skew correlates with c_log
- comparison against a random-edge-with-degree-cap baseline (globally random
  edge addition, not vertex-by-vertex)

## Construction Methods

| Method | Priority function |
|---|---|
| `high_degree` | Connect new vertex to highest-degree existing vertices |
| `low_degree` | Connect new vertex to lowest-degree existing vertices |
| `random` | Connect new vertex to random existing vertices |
| `max_neighbors` | Connect new vertex to vertices maximising shared neighborhood |

All methods check K₄-freeness before each edge addition and skip edges that
would create a K₄.

The `random_edge_capped` baseline adds edges globally (not vertex-by-vertex)
with a degree cap of √(N log N), which avoids the degree-gradient problem
entirely and serves as the comparison point.

## Usage

```bash
# Quick smoke test (N=10..20, 3 graphs per config)
micromamba run -n k4free python experiments/vertex_by_vertex/vertex_by_vertex.py --quick

# Full experiment
micromamba run -n k4free python experiments/vertex_by_vertex/vertex_by_vertex.py

# Custom
micromamba run -n k4free python experiments/vertex_by_vertex/vertex_by_vertex.py \
    --sizes 20 40 60 --methods high_degree random --graphs-per-config 20
```

## Output

- `results/results.csv` — one row per graph
- `results/summary.json` — aggregate stats per (method, N)
- `results/c_log_by_method.png` — c_log vs N for each method
- `results/degree_skew_vs_c.png` — gini coefficient vs c_log scatter

## Expected Results

All four vertex-by-vertex methods produce c_log ≫ 1 at N ≥ 30, with the
high-degree method worst (c ≈ 2–17 depending on N). The degree gini
coefficient will be strongly positively correlated with c_log. The
random-edge-capped baseline (c ≈ 1.1) outperforms every vertex-by-vertex
variant, confirming that the failure is structural to the vertex-by-vertex
approach and not fixable by choice of priority function.

## Conclusion

The degree-gradient is inherent to any vertex-by-vertex scheme: no priority
function can prevent early vertices from accumulating high degree. Edge-based
construction methods that operate globally (with a degree cap to enforce
regularity) are strictly better and should be preferred for any search over
K₄-free graphs.
