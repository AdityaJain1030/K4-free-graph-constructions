# experiments/alpha

Benchmarks for α solvers and proxies across structurally diverse K₄-free graphs.

## Files

| File | Purpose |
|---|---|
| `generate_graphs.py` | Shared graph source — 8 classes, ~96 graphs, used by both benchmarks |
| `bench_alpha_accuracy.py` | How well do cheap proxies (Caro-Wei, greedy MIS, clique UB) track true α? |
| `bench_alpha.py` | Head-to-head wall time + RSS for all exact solvers |
| `ALPHA_ACCURACY.md` | Results and guidance for proxy accuracy |
| `ALPHA_PERFORMANCE.md` | Results and guidance for solver performance |

For the mathematical foundations of each solver, see `docs/INDEPENDENCE_NUMBER.md`.

## Quick start

```bash
# Proxy accuracy across all graph classes
micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py

# Solver performance (skip solvers that time out on large graphs)
micromamba run -n k4free python experiments/alpha/bench_alpha.py --no-slow --timeout 30
```

Results land in `results/` as CSV + plots.
