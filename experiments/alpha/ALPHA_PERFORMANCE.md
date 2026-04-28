# α Solver Performance Benchmark

Wall-clock time and peak RSS for every exact α solver across all K₄-free graph
classes. Run with `bench_alpha.py` in this directory.

---

## Setup

One forked subprocess per solver (isolated peak RSS via
`resource.getrusage(RUSAGE_SELF).ru_maxrss`), per-solver wall-clock timeout.
Graphs come from `generate_graphs.py` — same 8 classes used in
`bench_alpha_accuracy.py`.

```bash
# All classes, skip solvers that time out on large graphs
micromamba run -n k4free python experiments/alpha/bench_alpha.py --no-slow --timeout 30

# Specific classes only
micromamba run -n k4free python experiments/alpha/bench_alpha.py \
  --classes synthetic_circulant prime_circulant --timeout 60

# Include slow solvers (alpha_exact, bb_numba, clique_complement)
micromamba run -n k4free python experiments/alpha/bench_alpha.py --timeout 120
```

`--no-slow` skips `alpha_exact`, `alpha_bb_numba`, and `alpha_clique_complement`,
which time out on graphs with n ≥ ~60 (see [Slow solver results](#slow-solvers)
below).

Outputs: `results/performance_results.csv` and `results/performance_plots/`

---

## Plots produced

| File | What it shows |
|---|---|
| `wall_time_by_class.png` | Wall time vs n per class, all solvers overlaid (log y) |
| `wall_time_heatmap.png` | Median wall time (ms) heatmap — class × solver |
| `rss_by_solver.png` | Median peak RSS per solver across all graphs |
| `timeout_rate.png` | Timeout rate (%) for class+solver pairs with at least one timeout |

---

## Results — median wall time by graph class

"—" = timeout at 30 s. Solvers: `bb_clique_cover`, `cpsat`, `cpsat_vt`, `maxsat`.

| Class | n range | bb_clique_cover | cpsat | cpsat_vt | maxsat |
|---|---|---:|---:|---:|---:|
| `prime_circulant` | 17–89 | 20 ms | 201 ms | 210 ms | 44 ms |
| `dihedral_cayley` | 20–68 | 1 ms | 202 ms | 210 ms | 34 ms |
| `polarity` | 31–91 | 884 ms | 497 ms | 279 ms | 3556 ms |
| `random_k4free` | 20–100 | 4 ms | 249 ms | 240 ms | 72 ms |
| `synthetic_circulant` | 20–300 | 1 ms | 217 ms | 221 ms | 27 ms |
| `brown` | 125 | 366 ms | 771 ms | 298 ms | 22072 ms |
| `sat_exact` | 10–20 | <1 ms | 201 ms | 207 ms | 28 ms |
| `near_regular` | 20–80 | 1 ms | 201 ms | 202 ms | 41 ms |

Polarity timeouts (n ≥ 133, 30 s budget):

| Graph | n | bb_clique_cover | cpsat | cpsat_vt | maxsat |
|---|---|---:|---:|---:|---:|
| ER(11) | 133 | timeout | 38 s | 12 s | timeout |
| ER(13) | 183 | timeout | — | — | timeout |

---

## Key findings

1. **`alpha_bb_clique_cover` is fast on sparse K₄-free graphs.**
   Sub-millisecond up to n=300 on circulants and Cayley graphs. Degrades badly
   on dense graphs: polarity ER(q) graphs (degree ~√n, dense triangle-free
   structure) push bb_clique_cover past 30 s at n=133.

2. **`alpha_cpsat_vt` is unsound on non-vertex-transitive graphs.**
   The `vertex_transitive=True` pin (`x[0]=1`) assumes vertex 0 participates in
   a maximum independent set — valid only for VT graphs. On random K₄-free
   graphs it under-reported α on 9 of 35 instances (disagreement confirmed by
   bb_clique_cover + cpsat + maxsat). Never use `cpsat_vt` unless the graph is
   provably vertex-transitive.

3. **CP-SAT is the right choice for dense graphs.**
   On polarity graphs where bb_clique_cover times out, `cpsat_vt` (with VT pin,
   valid here since polarity graphs are vertex-transitive) completes ER(11) in
   12 s. Plain `cpsat` takes 38 s. For unknown structure, plain `cpsat`.

4. **`alpha_maxsat` is fast on sparse graphs, terrible on dense ones.**
   27–72 ms on circulants and random graphs, but 22 s on the Brown graph and
   timeout on polarity ER(q) ≥ 11. Do not use on dense K₄-free graphs.

5. **CP-SAT has a 200–400 ms startup floor regardless of graph.**
   OR-Tools model build dominates at every n on sparse graphs. Not worth it when
   n ≤ 200 and the graph is sparse — use `bb_clique_cover`.

---

## Regime guide

| Graph shape | n | Recommended solver |
|---|---|---|
| Any sparse K₄-free (deg ≤ ~15) | any | `alpha_bb_clique_cover` |
| Dense K₄-free, vertex-transitive | any | `alpha_cpsat(..., vertex_transitive=True)` |
| Dense K₄-free, unknown structure | any | `alpha_cpsat(...)` |
| Sanity cross-check | any | `alpha_maxsat` (sparse only) |

---

## Slow solvers

`alpha_exact`, `alpha_bb_numba`, `alpha_clique_complement` all time out at
n ≥ ~60 on any non-trivial graph. From earlier runs on C(n,{1,2}):

| n | alpha_exact | bb_numba | clique_complement |
|---:|---:|---:|---:|
| 20 | <1 ms | 870 ms (JIT) | <1 ms |
| 40 | 129 ms | 908 ms | 65 ms |
| 60 | 79 s | 9.8 s | 20.6 s |
| 80 | timeout | timeout | timeout |

`bb_numba` adds 165 MB llvmlite overhead with no benefit over `bb_clique_cover`.
`clique_complement` is slow because the complement of a sparse K₄-free graph is
dense, making max-clique on the complement hard.

---

## Bug: cpsat_vt unsound on non-VT graphs

Discovered during this benchmark run. `cpsat_vt` reported α lower than the true
value on 9 of 35 random K₄-free instances, always under-counting. Root cause:
the VT pin fixes `x[0]=1`, which is only valid when every vertex is equivalent
under automorphisms. Random graphs have no such symmetry. The solver finds a
valid IS that includes vertex 0, but it may be smaller than the true maximum.

Use `cpsat_vt` only on circulants, Cayley graphs, and polarity graphs.
