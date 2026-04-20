# `BrownSearch` — Brown's C₄-free graph on F_q³

## What it does

Brown (1966): for odd prime q ≥ 5, the unit-distance graph on the
affine 3-space F_q³ has vertices F_q³ (|V| = q³) and edges

> (x, y, z) ~ (x', y', z')  iff  (x − x')² + (y − y')² + (z − z')² = 1 (mod q)

and is C₄-free (any two points have at most two common neighbours —
the intersection of two spheres in F_q³ is "small"). C₄-free implies
K₄-free (K₄ contains a C₄).

## Eligible N

| q  | N = q³ |
|----|--------|
| 5  | 125    |
| 7  | 343    |
| 11 | 1331   |
| 13 | 2197   |

q = 3 is technically defined but the sphere equation has too few
solutions for the graph to be interesting, so we skip it. Non-prime
q would again need GF(q) and is skipped.

## Why it exists

Polarity graphs hit N = q² + q + 1; norm graphs hit N = q² − 1;
Brown hits N = q³ — a third branch of the algebraic-family envelope,
at much larger N for small q.

## Kwargs

| kwarg  | hard/soft | meaning                                                |
|--------|-----------|--------------------------------------------------------|
| `rhs`  | soft      | Non-zero constant on the right of the sphere equation. |

All non-zero values of `rhs` give isomorphic graphs up to field
automorphism; exposed for completeness.

## Caveats

- **Build cost is O(|S| · q³)** with |S| ≈ q² (the number of
  length-1 3-vectors), so O(q⁵). At q = 13 that's ≈ 4 × 10⁵ edges
  visited — a few seconds.
- The graph is not regular unless F_q* is homogeneous enough
  (for small q there's mild degree variation).
- α(Brown) grows like q², so `c_log` lands in the 1.x range —
  this is an algebraic-ceiling data point, not a `c_log` winner.

## When **not** to reach for it

- Small N (< 100) — use `CirculantSearch` or `SATExact` for
  ground-truth comparisons.
- You need a finished competitive graph — `BrownSearch` alone
  isn't one.
