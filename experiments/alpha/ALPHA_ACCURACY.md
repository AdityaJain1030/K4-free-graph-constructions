# α Proxy Accuracy Benchmark

How well do cheap α proxies (Caro-Wei, greedy MIS, clique upper bound) track
the true independence number across structurally diverse K₄-free graphs?

---

## Running the benchmark

```bash
# Full benchmark — all 7 graph classes, 76 graphs, produces CSV + 7 plots
micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py

# Specific classes only
micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py \
  --classes prime_circulant sat_exact random_k4free

# More greedy restarts (more accurate but slower)
micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py --restarts 100

# Also benchmark CP-SAT timing per graph
micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py --cpsat

# Skip plots (CSV only)
micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py --no-plots
```

Outputs:
- `results/accuracy_results.csv` — per-graph raw numbers
- `results/accuracy_plots/` — 7 plots (see below)

Graph instances come from `generate_graphs.py`, which pulls from `graph_db`
where available and constructs on the fly otherwise. See that file for class
definitions and `--list` for available classes.

---

## Graph classes benchmarked

| Class | Description | N range | Graphs |
|---|---|---|---|
| `prime_circulant` | Best K₄-free C(n,S) at each prime n | 17–89 | 8 |
| `dihedral_cayley` | Best dihedral Cayley graphs (non-abelian) | 20–68 | 8 |
| `polarity` | Erdős-Rényi polarity graphs ER(q) | 31–91 | 4 |
| `random_k4free` | Random degree-capped edge addition | 20–100 | 35 |
| `brown` | Reiman-Brown R(3,k) graph | 125 | 1 |
| `sat_exact` | SAT-certified optima (highly irregular) | 10–20 | 11 |
| `near_regular` | random_regular_switch outputs | 20–80 | 9 |

---

## Proxies measured

| Proxy | Direction | Cost | Notes |
|---|---|---|---|
| `caro_wei` | lower bound | O(n) | Σ 1/(d(v)+1); degree-based, no structure |
| `greedy_mis` (`alpha_lb`) | lower bound | O(R(n+m)) | R random-restart greedy MIS |
| `clique_ub` (`alpha_ub`) | upper bound | O(nd) | greedy clique cover of G |

Paired as an `AlphaBracket(lb, ub)` — when lb == ub the bracket certifies
the exact value without SAT. See `utils/alpha_surrogate.py`.

---

## Full benchmark results (76 graphs, 7 classes)

Greedy MIS exact-match rate and max relative error across all classes:

| Class | Graphs | Greedy exact (%) | Greedy max rel err | Caro-Wei mean rel err |
|---|---|---|---|---|
| `sat_exact` | 11 | 100% | 0.000 | 0.328 |
| `dihedral_cayley` | 8 | 100% | 0.000 | 0.445 |
| `near_regular` | 9 | 89% | 0.071 | 0.632 |
| `prime_circulant` | 8 | 75% | 0.050 | 0.469 |
| `polarity` | 4 | 25% | 0.091 | 0.574 |
| `random_k4free` | 35 | 43% | 0.148 | 0.630 |
| `brown` | 1 | 0% | 0.150 | 0.798 |

Key takeaways:
- Greedy MIS is reliable on structured/regular graphs (SAT-exact, Cayley, near-regular)
- Greedy underperforms on sparse irregular graphs (brown, random) — use AlphaBracket to detect
- Caro-Wei is consistently poor as a ranking signal (mean rel err 33–80%) across all classes
- All exact solver runs completed in <50 ms per graph up to n=125

---

## Historical results (funsearch initial validations)

Early proxy correlation measured on 180 random-construction graphs
(60 per N ∈ {40, 60, 80}) — a narrower and less structured sample:

| N | Greedy MIS ρ | Caro-Wei ρ |
|---|---|---|
| 40 | 0.988 | 0.503 |
| 60 | 0.983 | 0.525 |
| 80 | 0.992 | 0.524 |

SAT timing on those graphs:

| N | mean (s) | max (s) | timeouts |
|---|---|---|---|
| 40 | 0.018 | 0.097 | 0 |
| 60 | 0.361 | 2.875 | 0 |
| 80 | 0.273 | 2.542 | 0 |

Zero timeouts. SAT is not a bottleneck up to at least N=80 — the surrogate
debate is moot at construction scale. For broader results across all 7 graph
classes, run the full benchmark above.

---

## Plots produced

| File | What it shows |
|---|---|
| `spearman_by_class.png` | Spearman ρ for each proxy, grouped by graph class |
| `relative_error_vs_n.png` | (true α − proxy)/true α vs n, per class |
| `proxy_scatter.png` | Proxy vs true α scatter for all three proxies |
| `greedy_error_dist.png` | Boxplot of greedy MIS absolute error per class |
| `bracket_width.png` | clique_ub − greedy_mis (bracket width) vs n |
| `exact_match_rate.png` | % graphs where greedy MIS == true α, per class |
| `solver_time_by_class.png` | alpha_bb_clique_cover wall time by class and n |

---

## When to use each proxy

| Situation | Use |
|---|---|
| n ≤ 200, any inner loop | Exact (`alpha_bb_clique_cover`) — fast enough |
| n > 200, ranking only | `alpha_lb` (greedy MIS, ≥20 restarts) |
| n > 200, certified value | `alpha_cpsat` with time limit |
| Bracket tightness check | `AlphaBracket` — if lb==ub you're done |
| Degree-only signal needed | Caro-Wei is fine as a floor, not a ranking signal |
