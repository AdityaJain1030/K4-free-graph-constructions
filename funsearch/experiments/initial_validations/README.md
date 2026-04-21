# K4-Free Independence Number Validation (Experiment 1)

## What This Tests

This experiment answers three questions before committing to a full FunSearch pipeline:

1. **SAT feasibility**: Can we compute exact independence number alpha(G) via SAT at N=40, 60, 80? How long does each call take? What's the timeout rate?

2. **Proxy correlation**: Do cheap estimates (Caro-Wei bound, greedy MIS) rank-correlate with true alpha? If Spearman rho > 0.7, surrogate scoring is viable for FunSearch's evolutionary loop.

3. **Construction signal**: Do structured priority functions (degree-based vertex selection) produce meaningfully different c-values than random construction? If there's variance, FunSearch has something to optimize.

The experiment builds ~180 K4-free graphs using 6 construction methods across 3 graph sizes, computes exact alpha via SAT binary search (PySAT Glucose4 + totalizer cardinality encoding), and compares against Caro-Wei and greedy MIS proxies.

## Prerequisites

Micromamba environment `funsearch` with Python 3.11:

```bash
micromamba create -n funsearch python=3.11 -c conda-forge -y
micromamba run -n funsearch pip install python-sat networkx numpy scipy matplotlib pandas tqdm
micromamba run -n funsearch bash scripts/setup_nauty.sh
```

## Quick Start

```bash
# Smoke test (~30 seconds, N=12, 2 graphs per config)
micromamba run -n funsearch python initial_validations/k4free_validation.py --quick

# Full experiment (~1-3 hours depending on hardware)
micromamba run -n funsearch python initial_validations/k4free_validation.py
```

## CLI Options

```
python k4free_validation.py [OPTIONS]

--sizes N [N ...]          Graph sizes (default: 40 60 80)
--methods M [M ...]        Construction methods (default: all 6)
--graphs-per-config K      Graphs per (N, method) pair (default: 10)
--outdir DIR               Output directory (default: results)
--workers W                Parallel workers (default: cpu_count // 2)
--sat-timeout SEC          SAT timeout per graph (default: 300)
--seed S                   Base random seed (default: 42)
--quick                    Quick smoke test (N=12, 2 graphs/config)
```

### Construction Methods

| Method | Description |
|--------|-------------|
| `degree` | Vertex-by-vertex, prefer connecting to high-degree vertices |
| `inverse_degree` | Vertex-by-vertex, prefer low-degree vertices |
| `random` | Vertex-by-vertex, random priority |
| `balanced` | Vertex-by-vertex, balance degree vs. neighborhood overlap |
| `random_edge` | Add random edges globally, skip K4-creating ones |
| `random_edge_capped` | Same as above with degree cap sqrt(N log N) |

## Output Format

### `results/results.json`

List of per-graph records:

```json
{
  "graph_id": 0,
  "n": 40,
  "method": "degree",
  "seed": 42,
  "num_edges": 187,
  "d_max": 12,
  "k4_free": true,
  "alpha_sat": 8,
  "sat_time_s": 1.234,
  "sat_timed_out": false,
  "build_time_s": 0.05,
  "caro_wei": 9.5432,
  "greedy_mis": 7,
  "c_value": 0.9654,
  "c_caro_wei": 1.1532,
  "c_greedy": 0.8456
}
```

### `results/summary.json`

Aggregate statistics: Spearman correlations, c-value stats by method/N, SAT timing.

### `results/plots/`

- `proxy_vs_alpha.png` — scatter plots of Caro-Wei and greedy MIS vs true alpha
- `c_value_by_method.png` — bar chart of c-values by construction method and N

## Expected Runtime

| N | SAT time/graph | Total (10 graphs x 6 methods, 8 workers) |
|---|----------------|------------------------------------------|
| 12 | < 1 second | ~10 seconds |
| 40 | 1-30 seconds | ~5-10 minutes |
| 60 | 10-120 seconds | ~15-45 minutes |
| 80 | 30-300 seconds | ~30-90 minutes |

Full experiment (N=40,60,80): **1-3 hours** with 8 workers. The dominant cost is SAT at N=80.

## Interpreting Results

### Proxy correlation (Spearman rho)
- **rho > 0.8**: Proxy is an excellent surrogate. FunSearch can use it directly.
- **rho 0.5-0.8**: Proxy preserves rough ranking. Hybrid scoring (filter with proxy, verify top candidates with SAT) is viable.
- **rho < 0.5**: Proxy is unreliable. Must use SAT for scoring, which limits FunSearch throughput.

### SAT timing
- **All solve < 60s**: SAT is fast enough for direct use in FunSearch (with ~100 evaluations).
- **Frequent timeouts at N=80**: Need surrogate scoring or limit FunSearch to N <= 60.

### c-value variance
- **Large variance across methods**: Priority function choice matters. FunSearch has meaningful signal to optimize.
- **Small variance**: All methods are equivalent. Need a different search space (e.g., block decomposition).

### Key invariants (checked automatically)
- `greedy_mis <= alpha_sat` (greedy finds a lower bound)
- `caro_wei <= alpha_sat` (Caro-Wei is a lower bound: alpha >= sum 1/(d(v)+1))
- All graphs must be K4-free (construction correctness)
