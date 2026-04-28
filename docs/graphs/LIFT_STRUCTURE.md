# Lift structure of the c_log frontier

Written 2026-04-24 while categorising every n ∈ [8, 100] by whether the
best connected K₄-free graph in graph_db beats, ties, or loses to the
best "trivial lift" (disjoint union of copies of a smaller cell). See
`SESSION_LOG_20260424.md` for session context.

## The lift identity

`c_log = α·d_max / (n·ln d_max)` is invariant under disjoint union:
k disjoint copies of a graph G have n' = k·n, α' = k·α, d'_max = d_max,
so c_log stays fixed. Therefore the frontier value at every composite n
is bounded above by the best c_log at any proper divisor n/k:

    best_lift(n) := min over d | n, d > 1 of best_c(n/d)

A *connected* K₄-free graph at n beats the trivial lift only if its
c_log is strictly below `best_lift(n)`. Below-lift connected graphs are
the only way to lower the frontier at that n below its cell-tiling
ceiling.

## The "primes" of the frontier

A handful of small irreducible cells set the floor by tiling upward:

| cell  | n  | α | d_max | c_log     | drives plateau at                     |
|-------|----|---|-------|-----------|---------------------------------------|
| P(17) | 17 | 3 | 8     | **0.6789**| n = 17, 34, 51, 68, 85                |
| 22-cell | 22 | 4 | 8  | 0.6995    | n = 22, 44, 66, 88                    |
| C_8²  | 8  | 2 | 4     | 0.7213    | n = 8, 16, 24, 32, 48, 56, 64, 72, 96 |
| n=14 cell | 14 | 3 | 6 | 0.7176  | n = 28, 42, 56, 70, 84, 98            |
| n=15 cell | 15 | 3 | 7 | 0.7195  | n = 30, 45, 60, 75, 90, 100           |

The P(17) floor at c = 0.6789 is the global minimum up to n ≤ 120 in
graph_db. Nothing in the current catalog breaks it at any n.

## Categorisation at n ∈ [8, 100]

Over the 71 n-values for which both a connected entry and a proper
divisor's best-c are known:

| category   | count | meaning                                              |
|------------|-------|------------------------------------------------------|
| **BEATS**  | 14    | Connected strictly improves on every trivial lift   |
| **TIES**   | 4     | Same c_log as the best lift                         |
| **WORSE**  | 46    | Best connected loses to the lift                    |
| **NO_CONN**| 7     | No connected entry; lift unchallenged               |

So roughly 80% of composite n are won (or tied) by disjoint-unions of a
prime cell. The BEATS set dominates only at small n (≤ 49).

### BEATS — connected genuinely wins (14 n)

| n | lift (α, d, c) | connected (α, d, c) | mechanism |
|---|---|---|---|
| 8  | (4, 3, 1.365) | (2, 4, **0.721**) | α: 4→2, d: 3→4 |
| 10 | (4, 3, 1.092) | (3, 4, **0.866**) | α: 4→3, d: 3→4 |
| 12 | (4, 3, 0.910) | (3, 5, **0.777**) | α: 4→3, d: 3→5 |
| 14 | (4, 4, 0.824) | (3, 6, **0.718**) | α: 4→3, d: 4→6 |
| 15 | (6, 3, 1.092) | (3, 7, **0.719**) | α: 6→3, d: 3→7 |
| 18 | (6, 3, 0.910) | (4, 6, **0.744**) | α: 6→4, d: 3→6 |
| 20 | (6, 4, 0.866) | (4, 7, **0.719**) | α: 6→4, d: 4→7 |
| 21 | (6, 4, 0.824) | (4, 8, **0.733**) | α: 6→4, d: 4→8 |
| 22 | (6, 4, 0.787) | (4, 8, **0.699**) | α: 6→4, d: 4→8 |
| 25 | (10, 3, 1.092)| (6, 6, **0.804**) | α: 10→6, d: 3→6 |
| 27 | (9, 3, 0.910) | (5, 10, **0.804**)| α: 9→5, d: 3→10 |
| 33 | (9, 4, 0.787) | (5, 12, **0.732**)| α: 9→5, d: 4→12 |
| 36 | (8, 6, 0.744) | (6, 10, **0.724**)| α: 8→6, d: 6→10 |
| 49 | (14, 4, 0.824)| (8, 12, **0.788**)| α: 14→8, d: 4→12 |

**Mechanism, universal**: every BEATS winner trades an **α saving**
(fewer independent vertices than the lift's k·α_cell) for a **higher d**
(by 1 to 8). The c_log formula rewards this because `d/ln d` is
sub-linear — halving α allows quadrupling d and still winning.

Break-even: connected beats the lift iff
`α_conn/(k·α_cell) · d_conn/d_cell · ln(d_cell)/ln(d_conn) < 1`.

**Structural commonalities of the 14 BEATS winners:**

- 12 / 14 are Cayley graphs with explicit connection sets. The two
  exceptions (n=14, 15) are `sat_exact` near-regular non-VT graphs.
- All have girth 3. They are *K₄-maximal*: many triangles without
  forming K₄.
- α/θ tightness moderate (0.65–0.95) — SDP alone doesn't explain
  winning; the mechanism is combinatorial.

### TIES (4 n)

| n  | = k·p  | connected | lift |
|----|--------|-----------|------|
| 16 | 2·8    | α=3, d=8  | 2×C_8² (α=4, d=4) |
| 26 | 2·13   | α=6, d=6  | 2×(n=13 cell) |
| 46 | 2·23   | α=6, d=16 | 2×(α=6, d=4 at n=23) |
| 58 | 2·29   | α=8, d=16 | 2×(n=29 cell) |

All four are n = 2·p with p (near-)prime, and the connected sits on the
same iso-c_log curve as the lift via higher-d / lower-α trade. Notable:
**n=46 is *not* a lift of 2·(n=23)** — its Z_46 Cayley connection set is
not closed under +23 mod 46, so it's genuinely a Z_46-specific
construction that happens to tie.

### WORSE (46 n) — three regimes

Ordered by loss magnitude:

1. **Pure blowup of the prime cell** (biggest losses, Δ > 0.2): at n =
   34 (+0.340), 51 (+0.654), 87 (+0.766), 100 (+0.482), 88 (+0.214),
   80 (+0.209). A k-blowup preserves α (α = k·α_cell) but multiplies
   d by k. The disjoint-union lift always strictly dominates any
   blowup: same α, smaller d, lower c_log.

   **Rule:** never submit a blowup as a frontier candidate. Compare
   to its disjoint-union counterpart first.

2. **Near-miss overshoots** (Δ < 0.05): n = 24 (+0.003), 60 (+0.004),
   36 (+0.020), 54 (+0.020), 96 (+0.043), 48 (+0.043). Connected
   saves 1–2 α but pays 3–8 d. Break-even-d tuned SAT should close
   these.

3. **α-regression losers** (13 of 46): connected actually has *higher*
   α than the lift AND higher d — strict loss on both axes. Usually
   `cayley_tabu_gap` or `circulant_fast` heuristics picking too many
   edges.

### NO_CONN (7 n)

No connected entries in DB at these n: **n ∈ {44, 65, 66, 68, 72, 85,
98}**. All are multiples of prime cells (8, 13, 14, 17, 22). The lift
plateau is the only data point. A connected K₄-free construction at
any of these would be novel regardless of c_log improvement.

## Triangle density is not the signal

Early hypothesis tested and **rejected**: that BEATS winners are
winning by being triangle-dense. Normalised by the K₄-free Mantel cap
`⌊d²/4⌋ per vertex` (from the triangle-free-neighbourhood
requirement), the BEATS graphs sit at **17–25% Mantel saturation** —
Paley-17 is the highest at exactly 25%.

By contrast the WORSE graphs, especially blowups, sit at **50–75%**
saturation. Triangle density is the *anti-signal*.

So when searching for BEATS-style connected winners, **don't optimise
for triangle count**. The right objective is α·d subject to K4-freeness,
not triangles per vertex.

## Implications for search

1. **BEATS regime is below n ≈ 50.** Above that, the prime cells tile
   too efficiently for connected constructions to win by the
   α-trade-for-d mechanism at typical search-produced (α, d) pairs.

2. **To break the P(17) floor**, find a connected K4-free graph at any
   n with α/n < 3/17 = 0.176 and d such that α·d/ln d is below
   `17·8/ln 8 = 65.37`. No known construction does this. The
   `P17_LIFT_OPTIMALITY.md` verification programme has confirmed no
   cyclic Cayley graph does, up to k=3 (N=17, 34, 51).

3. **NO_CONN n are free targets**: any connected K₄-free construction
   at n ∈ {44, 65, 66, 68, 72, 85, 98} is a new data point, even
   without a c_log improvement. Particularly at n = 68 = 4·P(17)
   where the disjoint-union lift is at the global floor 0.6789.

4. **Search methods spread across disjoint symmetry classes.**
   Cayley-tabu lives in spread-0 (vertex-transitive) configurations;
   sat_exact / sat_near_regular_nonreg live in spread-1 (near-regular
   non-VT) configurations. These classes don't intersect. Rules
   learned from one family don't port to the other by edge-level
   sparsification.

## Appendix: n=83 as a Ramsey-bounded example

The analysis of why α=7 at n=83 is provably infeasible (and why α=13
is at the n^(3/5) scale, not at any theoretical lower bound):

| bound                             | α ≥  | tight when              |
|-----------------------------------|------|-------------------------|
| Ramsey R(4, α+1) > n              | 8    | always; α=7 infeasible  |
| Caro-Wei                          | 4.4  | G = union of cliques    |
| K3-free Shearer (1983)            | 10.1 | G is triangle-free      |
| K4-free Bollobás-type             | 6.7  | asymptotic              |
| Empirical n^(3/5)                 | 14.2 | Cayley-class extremals  |
| MV n^(2/5)                        | 5.9  | incidence-geometry      |

The current α=13 at (n=83, d=18) is at 0.92 of the n^(3/5) scale —
saturated on the Cayley-class empirical curve but nowhere near any
proven lower bound. To go below α=10 at n=83 would require
Mattheus-Verstraete-style incidence constructions, not Cayley methods.
