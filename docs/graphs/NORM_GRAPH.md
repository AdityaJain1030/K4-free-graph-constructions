# `NormGraphSearch` — projective-norm Cayley graph

## What it does

Probe 5b (algebraic ceiling). For prime `q` and n = q² − 1:

- Identify F_{q²}^* with Z_{q²−1} (both are cyclic of order q² − 1).
- Compute the connection set `K` corresponding to the kernel of the
  norm map `N: F_{q²}^* → F_q^*`, `N(x) = x^{q+1}`. Under the cyclic
  identification this kernel is `{(q−1)·k mod (q²−1) : k = 0..q}`.
- Build the Cayley graph `Cay(Z_{q²−1}, K)`.

Result: an algebraically-distinguished circulant on n = q² − 1
vertices, regular of degree `|K|`, with a normal spectrum inherited
from Gauss sums.

## Eligible N

| q  | N = q² − 1 |
|----|------------|
| 3  | 8          |
| 5  | 24         |
| 7  | 48         |
| 11 | 120        |
| 13 | 168        |
| 17 | 288        |
| 19 | 360        |

Non-prime prime-powers (q = 4, 8, 9, …) are skipped on purpose — the
F_{q²} arithmetic would need `galois` and isn't worth the dependency
for a probe.

## Why it exists

For N ≤ 35 `CirculantSearch` enumerates everything exhaustively, so
this search adds nothing there. It earns its keep at N ≥ 48 where
exhaustive circulant search is infeasible and there's no principled
algebraic way to pick a connection set without external input. The
norm-kernel pick is the canonical one and the one closest to the
"projective norm graph" family underlying the Mattheus–Verstraëte
construction.

## Constructor

No kwargs beyond the base triad. Provide `n`; search is a no-op if
`n ≠ q² − 1` for any prime `q`.

## When **not** to reach for it

- You want a competitive `c_log` out of the box — this is a probe
  of the algebraic ceiling, not a winner.
- N is small enough (≤ 35) for `CirculantSearch` — it will enumerate
  the same graph alongside many others, more informatively.
