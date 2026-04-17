# Baselines Summary

- Runtime: **0.4 min**
- Methods run: method1, method2, method2r, method3, method3b, method4
- N range: 6..20

## 1. Final-20 mean c per method (attractor value)

| method | mean c (last 20 N) | samples |
|--------|---------------------|---------|
| method1 | 0.9559 | 15 |
| method2 | 1.2128 | 15 |
| method2r | 1.0672 | 15 |
| method3 | 0.9899 | 15 |
| method3b | 0.9850 | 15 |
| method4 | 0.9899 | 15 |

## 2. Gap to SAT-optimal at overlap (N=12..35)

> ⚠️ **Caveat:** The "SAT-optimal" column below reads directly from
> `SAT/k4free_ilp/results/pareto_n{N}.json`. Those ILPs were time-limited
> (600s–1800s) and **did not prove optimality** for N ≥ 26. Indicators:
> N=25 gives c=0.72 (α=5, d=7) but N=26 jumps to c=0.93 (α=5, d=12) —
> adding one vertex should not double d_max. N=32+ shows c=1.55+, which
> is worse than random baselines — clearly non-optimal. The reference
> is reliable only for N ≤ 25.

| N | SAT | method1 | method2 | method2r | method3 | method3b | method4 |
|---|-----|---|---|---|---|---|---|
| 12 | 0.777 | 0.910 | 1.294 | 1.036 | 0.962 | 0.962 | 0.962 |
| 13 | 0.773 | 0.888 | 1.195 | 0.956 | 1.030 | 1.030 | 1.030 |
| 14 | 0.718 | 0.957 | 1.109 | 1.109 | 1.030 | 0.957 | 1.030 |
| 15 | 0.720 | 0.962 | 1.116 | 1.116 | 0.962 | 0.962 | 0.962 |
| 16 | 0.721 | 1.024 | 0.962 | 0.962 | 0.971 | 0.971 | 0.971 |
| 17 | 0.679 | 0.914 | 1.131 | 1.131 | 0.985 | 0.985 | 0.985 |
| 18 | 0.744 | 0.962 | 1.069 | 1.069 | 0.962 | 0.962 | 0.962 |
| 19 | 0.705 | 0.981 | 1.215 | 1.215 | 1.063 | 1.063 | 1.063 |
| 20 | 0.720 | 0.962 | 1.086 | 1.086 | 1.010 | 1.010 | 1.010 |
| 21 | 0.733 | — | — | — | — | — | — |
| 22 | 0.745 | — | — | — | — | — | — |
| 23 | 0.753 | — | — | — | — | — | — |
| 24 | 0.721 | — | — | — | — | — | — |
| 25 | 0.720 | — | — | — | — | — | — |
| 26 | 0.929 | — | — | — | — | — | — |
| 27 | 0.894 | — | — | — | — | — | — |
| 28 | 1.030 | — | — | — | — | — | — |
| 29 | 0.995 | — | — | — | — | — | — |
| 30 | 1.113 | — | — | — | — | — | — |
| 31 | 1.148 | — | — | — | — | — | — |
| 32 | 1.557 | — | — | — | — | — | — |
| 33 | 1.619 | — | — | — | — | — | — |
| 34 | 1.649 | — | — | — | — | — | — |
| 35 | 1.649 | — | — | — | — | — | — |

## 3. Convergence

- **method1**: no stable convergence detected (final rolling c=0.9618)
- **method2**: no stable convergence detected (final rolling c=1.0857)
- **method2r**: no stable convergence detected (final rolling c=1.0857)
- **method3**: no stable convergence detected (final rolling c=1.0099)
- **method3b**: no stable convergence detected (final rolling c=1.0099)
- **method4**: no stable convergence detected (final rolling c=1.0099)

## 4. Structural similarity

- 49 pairs of (method1, method2, N) produced isomorphic graphs.
- Per-pair mean Jaccard (canonical edge sets) — see `comparison_summary.md`.

## 5. Attractor questions

1. **c stabilizes**: partially — all final-20 c values within 0.257 of each other.
2. **Methods agree on c?** range 0.956..1.213
3. **Best method (lowest attractor c)**: method1 (c≈0.956)
4. **Worst**: method2 (c≈1.213)
5. **Does regularity (M3) match α-aware (M3b, M4)?** See final-20 means above.
6. **Does block structure (M2) help?** Compare M2 vs M1/M3.

## 6. Runtime per method (mean over best-of-sweep)

| method | mean time/run (s) |
|--------|--------------------|
| method1 | 0.00 |
| method2 | 0.09 |
| method2r | 0.09 |
| method3 | 0.02 |
| method3b | 0.02 |
| method4 | 0.02 |

See `c_vs_N.png`, `d_vs_N.png`, `variance_vs_N.png`, `jaccard_vs_N.png` for trends.