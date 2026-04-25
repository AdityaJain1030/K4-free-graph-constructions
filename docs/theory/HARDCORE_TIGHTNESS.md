# Hardcore (occupancy) upper bound on α across the DB

Ran the exact hard-core measure `ρ_v(G,λ) = λ·Z(G−N[v],λ)/Z(G,λ)`, took
`E_max(G) = max_λ Σ_v ρ_v`, compared to true α. This is the tightest α
upper bound reachable by any single-fugacity hard-core / local occupancy
method (Davies-Jenssen-Perkins-Roberts ceiling).

**273 unique K4-free graphs with N≤22** (compute-bound by `2^N`; runs in
<1s total).

## Tightness (E_max / α) by N

| N | #graphs | mean E/α | min E/α | max E/α | frac ≥ .95 |
|---|---|---|---|---|---|
| 4–22 | 273 | **0.997** | **0.961** | 0.998 | **100%** |

Every single graph in the cache sits at E_max / α ≥ 0.961, and the vast
majority at ≥ 0.995. The 0.998 ceiling is a numerical artifact (finite
λ_max=200 in the grid; true limit at λ→∞ is exactly α). For the method's
purposes this is "tight".

## By d_max

Nothing breaks this pattern: every d_max bucket (1..10) shows mean
tightness 0.996–0.998.

## The handful of "least local" α

| N | d_max | α | c_log | E_max | E/α | regular? |
|---|---|---|---|---|---|---|
| 19 | 4 | 7 | 1.063 | 6.726 | **0.961** | yes |
| 16 | 7 | 4 | 0.899 | 3.925 | 0.981 | yes |
| 14 | 4 | 5 | 1.031 | 4.921 | 0.984 | no |
| 13 | 4 | 5 | 1.110 | 4.935 | 0.987 | no |
| 12 | 7 | 5 | 1.499 | 4.942 | 0.988 | no |

All of these are "bad" graphs (c_log ≥ 0.9) — they have an α that the
hard-core measure underestimates by ~4%, but they're not frontier
graphs. The tightness loss correlates with **low d_max relative to α**
(bloated independence that's hard to pick up locally).

## The "most local" α (tied at the numerical ceiling)

Includes **P(17)** (N=17, d=8, α=3, c_log=0.6789, E/α=0.998) and every
frontier-plateau graph. The extremizers we actually care about — Paley,
C(22), CR(19), their blow-ups, the SAT-exact near-regulars — all sit at
the numerical ceiling.

## Interpretation

The explored subset has **very local α across the board**. This matches
the theoretical claim in `docs/theory/SUBPLAN_B.md` §11: hard-core
already captures α(G) to ~99% on every K4-free graph we've built, and
P(17) saturates the hard-core method almost exactly.

**Consequence for bounds:**
- Any single-fugacity occupancy-method argument can recover α to within
  a fraction of a percent for our frontier. The ceiling of c_log you can
  derive this way is essentially the observed c_log.
- In particular, the universal lower bound `c(K4-free) ≥ ?` via
  hard-core cannot beat the empirical min over the DB by a meaningful
  margin — `E_max·d_max/(N·ln d_max)` comes out within ~0.3% of the
  observed c_log on every frontier graph.
- If we want a bound strictly below P(17)'s 0.6789, hard-core alone
  won't do it. Need a method that sees global structure the hard-core
  measure misses (Lovász θ with added constraints, flag algebra with
  higher-order moments, or an SDP with non-local clique cuts).

**The one outlier worth re-examining** is the N=19 d=4 α=7 row at
tightness 0.961 — that's an ~4% gap. That graph is in the DB as regular
c_log=1.063 (not a frontier row), so it's far from the extremizer, but
it's the *type* of structure where hard-core leaves the most slack. If
you're hunting for non-local α, low-degree regular graphs with large α
are where to look — but they live above the frontier, so it's mostly a
curiosity.

## Artifacts

CSV written to `results/hardcore_tightness.csv` (273 rows: `n, d_max,
alpha, c_log, E_max, tightness, is_regular, graph_id`).
