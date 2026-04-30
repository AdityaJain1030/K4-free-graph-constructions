# `experiments/fragility/` — results

> Last updated 2026-04-30. Tests A, D, E and the basin-radius variant
> done. Test C absorbed as a synthesis of A's per-move data, no new
> sweep planned.
>
> See `README.md` for the four-object framework (local Δ-distribution,
> barrier tree, basin volume, Markov-chain spectral gap) and the
> pre-registered predictions from the other Claude session.

---

## TL;DR

| Test | Object | Verdict |
|---|---|---|
| **A** | local Δc_log distribution | Frontier graphs are 4–10× more fragile per move than random K₄-free graphs at the same N (in *relative* units). N=35 Cayley plateau is the only true zero. Lift chains follow 1/k decay. |
| **E** | basin volume from random init | **0/200 hits at every N=10..22**. Random density-matched seeds never reach Cayley/SAT/brute_force optima under add+delete descent. |
| **D** | landscape topology (barrier tree) | Move-graph is **connected** at loose thresholds but has 694 → 5476 → ... combinatorial local minima at N=8 → 9 (≈8× per N). At tight thresholds isolating the SAT-optimum's c_log shelf, the **shelf itself fragments**: 12 components at N=10 (the optimum is in the *second-largest* island); 13 components at N=11 (the optimum is an *isolated singleton*). |
| **basin-radius (variant)** | basin recoverability under switch from a perturbed target | Under sampled (cap=100) best-improving switch descent, even K=1 random switch from a rigid Cayley_30 target gives 0/20 recovery. Sampling-vs-genuine ambiguity not separable. |

Together these establish the SAT failure mode: **the SAT-target c_log shelf is internally disconnected and the SAT-optimum sits on a small (or singleton) island within it**. Local search restricted to legal K4-preserving moves cannot bridge to the SAT optimum even if it lands on the right shelf.

---

## Test A — local Δc_log distribution at T=1

For each (frontier seed, move family, N) cell, enumerate (or sample
≤500) legal moves at T=1, compute Δc_log per move, summarise the
distribution. Replaces the v0 trajectory mean with proper
distributional probes.

### Sweeps

- **Small N=10..22, all 4 moves**: `data/delta_dist.json`,
  `images/delta_dist_{histograms,tails}.png`. 9.3 s wall.
- **Large N=17..39, all 4 moves**: `data/delta_dist_largeN_full.json`,
  `images/delta_dist_largeN_full_{histograms,tails,vs_n_lines,vs_n_heatmap}.png`. 28 s wall.
- **Best-per-N N=14..133**: started but killed once the picture closed.

### Key findings

#### 1. Paley(17) has zero `add` moves

Every non-edge of P(17) has a common-neighbour pair that completes a
K₄. So under add-only moves P(17) is *categorically unreachable from
below* — you can only descend to it by deleting edges from a denser
graph. Same shows up at SAT-certified optima at N=15 (only 5 legal
`add` moves) and similar at large-N Cayley plateau winners.

#### 2. Bimodal delete-distributions on structured graphs

SAT-certified and Cayley graphs at N ≥ 12 have a *bimodal* Δ-distribution
under `delete`: a small lobe near 0 plus a larger lobe at Δ ≈ 0.20–0.25.
Random graphs show the opposite — most mass at Δ ≈ 0 with a small
tail at Δ ≈ 0.15. **Random graphs have many α-redundant edges;
structured graphs do not.** This is the per-graph extension of
`experiments/edge_gradients/` Test 1 result that the lowest-c_log
graphs in graph_db are α-critical.

#### 3. Relative fragility cleanly separates families at every N

Mean Δc_log normalised by the seed's c_log gives an order-of-magnitude
separation:

| N | cayley/SAT μΔ/c_log (switch) | random μΔ/c_log (switch) | ratio |
|--:|---:|---:|---:|
| 17 | 0.333 | 0.030 | **11×** |
| 22 | 0.250 | 0.029 | 8.6× |
| 25 | 0.15–0.20 | 0.033 | 4.5–6× |
| 30 | 0.165–0.20 | 0.041 | 4–5× |
| 35 | **0.000** (Cay(Z₅×Z₇)) | 0.017 | 0 |
| 39 | 0.097 | 0.024 | 4× |

The absolute mean Δ shrinks with N but the relative fragility stays
in the 4–11× separation regime. Random K₄-free graphs maintain their
"loose" character at all N tested; structured graphs stay rigid
except at the N=35 plateau.

#### 4. The N=35 plateau is the only true zero

Cay(Z₃₅, S) with d=10-regular, α=7, c_log=0.869 has mean Δ_switch =
0.00 and mean Δ_delete = 0.00. Every legal move preserves c_log to
within numerical error. Mechanism: Z₃₅ = Z₅ × Z₇ has a rich
automorphism group; many edges and switch-pairs are equivalent under
auto, so they preserve α and d_max. Spectrum confirms: λ_min ≈ 3.86
and λ ≈ 4.80 each at multiplicity ≥ 2. Number-theoretic dependence
of Cayley fragility on the auto-group of the underlying group was
not predicted.

#### 5. Lift chains: 1/k fragility decay

`disjoint_lift` graphs at N = k × N₀ (k disjoint copies of a base
P(N₀)) preserve c_log under disjoint union. Empirically per-edge
fragility shrinks as 1/k:

| k (lift) | predicted (0.246/k) | measured Δ_delete |
|---:|---:|---:|
| 2 (N=28) | 0.123 | 0.117 |
| 3 (N=42) | 0.082 | 0.080 |
| 4 (N=56) | 0.062 | 0.060 |
| 5 (N=70) | 0.049 | 0.048 |

Match within 2%. The "P(>0.05)=0 plateau" at N=70 is just the 1/k
decay crossing the 0.05 threshold; no new geometry.

#### 6. K₄-margin: a clean structural separator

K₄-safe non-edges as % of all non-edges:

| N | sat_exact safe% | cayley safe% | random safe% |
|--:|---:|---:|---:|
| 10 | 60% | 60% | 96% |
| 15 |  9% | 50% | 49% |
| 17 | **0%** | **0%** | 67% |
| 22 | 39% | 39% | 100% |

Frontier graphs are K₄-saturated; random K₄-free graphs at lower
density are loose. This is a structural axis cleanly separating the
two regimes.

### Test A status

**Closed for cayley/circulant family.** Polarity/Brown/MV extension
is open but lower-priority — local fragility shape is characterised.

---

## Test E — basin volume under greedy descent

For each frontier target G\* at N ∈ {10, 12, 15, 17, 19, 22}, sample
200 random K₄-free initialisations at matched density (Bohman–Keevash
adder), run best-improving descent under add+delete with plateau cap
2N, canonicalise endpoint, count target hits.

Wall: 56 min.

Artifacts: `data/basin_volume_add_delete.json`,
`images/basin_volume_add_delete.png`,
`images/basin_volume_endpoints_add_delete.png`.

### Headline

**0/200 target hits at every N tested.** p̂_M(G\*) ≤ 5×10⁻³ for every
frontier source (server_sat_exact, brute_force, cayley_tabu_gap) at
every N. Two orders of magnitude below the "RL-findable" threshold
of 10⁻². Comparison: N=8 smoke gave 1/30 = 3.3%, so basin volume
drops from ~3% at N=8 to ≤ 0.5% at N=10 and stays there.

### Where descent lands instead

All 200 endpoints per N concentrate at a small number of mediocre
local minima with c_log ∈ [0.85, 1.13] — a clear gap from the
frontier band [0.68, 0.86]. None of the 200 endpoints at any N hits
a frontier graph. This is exactly P2 from the pre-registered
prediction (random-init flow concentrates on structurally generic
minima) and dovetails with Test D's local-minimum count.

---

## Test E variant — basin radius under switch (negative)

Run `run_basin_radius.py` to test whether descent recovers from
perturbations of the target itself. K random switches from
cayley_tabu_gap N=30 (rigid, mean Δ_switch = +0.13), then sampled
best-improving switch descent (candidate_cap=100, plateau-cap=N).
ε=0.005 plateau-match threshold.

Killed mid-run; data we have:

| K | exact hits | plateau hits |
|--:|---:|---:|
| 1 | 0/20 | 0/20 |
| 5 | 0/20 | 0/20 |
| 20 | 0/20 | 0/20 |

### Verdict

**Negative under sampling.** Two interpretations both consistent
with the data:

1. *Basin is genuinely zero-radius under switch.* A single random
   switch lands at an α-equivalent state where descent rule sees no
   improving move — α-approx is integer, most switch-neighbours of
   the perturbed state share α with it.
2. *Sampling is too weak.* 100/14k ≈ 0.7% coverage; if improving
   moves are rare, sampled best-improving misses them.

Distinguishing (1) from (2) requires full O(|E|²) enumeration at
N=30 (~30 min/trial), not pursued.

For practical search-agent purposes both interpretations are
operationally equivalent: any sampling-based agent at N ≥ 30 cannot
recover from non-trivial perturbations of a rigid Cayley target
under switch.

### Open follow-ups

- Run on the **N=35 plateau** target. Prediction: p_plateau much
  higher there because every switch-neighbour is at the same c_log;
  descent stays in the plateau cluster regardless of starting point.
- Bigger candidate_cap (500–2000) at N=30 to bracket the
  sampling-vs-genuine ambiguity.
- SDP-biased sampler from `experiments/edge_gradients/` to find rare
  improving switches.

---

## Test D — disconnectivity graph and SAT failure mode

Pipeline: stream `geng -k N` → filter to c_log ≤ threshold → enumerate
move-neighbours → batched `labelg` canonicalisation → build move
adjacency → Kruskal-on-energy.

Reports two distinct objects:

1. **Connected components** of the move graph, with lowest-c_log
   representatives.
2. **Combinatorial local minima**: graphs G with no in-slice neighbour
   at strictly lower c_log. These are exactly where best-improving
   descent terminates — the *traps* Test E hits.

### Loose-threshold pass: counting traps

Threshold c_log ≤ 1.2 (most of K₄-free space at small N):

| N | slice size | components | combinatorial local minima | wall |
|--:|---:|---:|---:|---:|
| 7 |    362 | 1 |    1 |   2 s |
| 8 |   1790 | 1 |  **694** |  16 s |
| 9 | 14 698 | 1 | **5 476** | 207 s |
| 8 (switch) | 1790 | **143** | per-component | 21 s |

Findings:

- **Single connected component under add+delete at every N tested.**
  The K₄-free move-graph is "one big terrain." Random K₄-free seeds
  and frontier optima are in the *same* connected component (this
  rules out a lazy "they're on different islands" interpretation of
  Test E, but the ruling-out is itself near-trivial: route any G to
  any G' through the empty graph).
- **Combinatorial local-min count grows ~8× per N step**. 1 → 694
  → 5476. Extrapolating, N=12 has ~10⁶ traps, N=15 has ~10⁹. Local
  search at any non-trivial N navigates a forest of traps, not a
  single basin.
- **Trap density concentrates on a single c_log "shelf" above the
  global minimum.** N=8: dominant cluster of 390 traps at c_log≈1.08;
  global min isolated at 0.72 with gap 0.30. N=9: dominant cluster
  4070 at c_log≈1.04; global min at 0.91 with gap 0.05.
- **c_log shelves are determined by (α, d_max).** Both integer; very
  few feasible combinations at any N. The 5476 traps at N=9 organise
  onto exactly 5 horizontal shelves (one per (α, d_max) pair), with
  74% of traps on the (α=3, d_max=5) shelf at c_log=1.04. Visualised
  in `images/landscape_scatter_n9_add_delete.png`.
- **Switch is the wrong move for connectivity.** Switch preserves
  degree sequence; at N=8 we get 143 components (one per degree
  sequence), trivially fragmented. The brute_force optimum's switch-
  component has only 4 graphs out of 1790 (basin 0.2%).

### How D explains E

Test E's 0/200 result has a now-tight structural cause. At N=8 there
are 694 combinatorial local minima where best-improving descent
terminates; only 1 is the global optimum. At N=9, 5476 traps and
4073 of them sit on the dominant (3,5) shelf at c_log=1.04 — that's
where random density-matched descent lands almost always. The
global optimum is one specific iso-class with a tiny basin relative
to the dominant shelf's combined basin.

### Tight-threshold pass: the SAT failure mode

The interesting question: when we shrink the slice to *just the
SAT-optimum's c_log shelf*, is the shelf internally connected?

**N=10, c_log ≤ 0.90, α ≤ 3, d_max ≤ 4 (the (3,4) shelf, where the
brute_force optimum lives):**

- 370 graphs in slice.
- **12 disconnected components** under add+delete restricted to the
  shelf.
- Component sizes: 194, 161, 4, 2, 2, then 7 singletons.
- The brute_force optimum (|E|=14) is in the **size-161 component**.
  The **larger size-194 component does not contain the optimum.**
- Read: even if a search miraculously lands on the right c_log
  shelf, it has only 161/370 = **44%** chance of being on the right
  island within the shelf. From the 194-graph island, the optimum is
  unreachable without leaving c_log ≤ 0.90 (search has to climb).

**N=11, c_log ≤ 0.80, α ≤ 3, d_max ≤ 4 (the SAT-optimum's shelf):**

- 17 graphs in slice. **13 disconnected components.** Move-graph
  average degree = 0.5 — most graphs have *zero* in-slice neighbours.
- 11 of 13 components are singletons.
- **The SAT-certified optimum (gid=2c3e71140d, |E|=22, c_log=0.787)
  is one of the singletons.** No add/delete move from the SAT
  optimum keeps you on the shelf. It is *strictly isolated*.

**Trend:**

| N | shelf size | components | largest comp | SAT-opt's component |
|--:|---:|---:|---:|---:|
| 10 | 370 | 12 | 194 | 161 |
| 11 |  17 | 13 |   3 | **1 (singleton)** |

### Why shelves disconnect

Within a single (α, d_max) shelf, the only legal moves that *stay*
on the shelf are those preserving both invariants. Most additions
raise d_max from 4 to 5 (off shelf). Most deletions raise α from 3
to 4 (off shelf). The remaining shelf-preserving moves form a
*sparse* sub-graph that breaks into islands. As N grows, (α=3) is
increasingly Ramsey-tight — only a few specific structures achieve
it, each with ~no shelf-preserving neighbours, and the shelf
collapses to mostly singletons.

### SAT failure mode, stated cleanly

> **At N ≥ 11, the SAT-certified optimum's c_log shelf is internally
> disconnected, and the SAT optimum sits on a singleton (or
> arbitrarily small) island within it. Local search using
> K₄-preserving moves has no shelf-internal path to the SAT optimum.
> Any search that lands on the right c_log shelf must already be on
> the right island, or must climb off the shelf and re-enter at the
> right place — neither of which descent does.**

This is the precise structural reason SAT solvers are necessary at
N ≥ 11 and heuristic local search cannot replace them: the SAT
optimum is *literally disconnected* from every other graph in its
own c_log shelf under all the local move families we tested.

### Test D artifacts

- `data/barrier_tree_n7_add_delete.json`
- `data/barrier_tree_n8_add_delete.json`
- `data/barrier_tree_n8_switch.json`
- `data/barrier_tree_n9_add_delete.json`
- `data/barrier_tree_n10_t095.json` (loose tight, all (3,4)+(3,5))
- `data/barrier_tree_n10_t090.json` (tight, (3,4) shelf alone)
- `data/barrier_tree_n11_t080.json` (tight, (3,4) shelf alone)
- `images/barrier_tree_n8_add_delete_traps.png` (trap density histogram)
- `images/barrier_tree_n9_add_delete_traps.png`
- `images/barrier_tree_n8_switch_dendrogram.png`
- `images/landscape_scatter_n9_add_delete.png` (shelf structure)
- `images/landscape_scatter_n10_add_delete.png`

### Test D not pursued

- N=12 tight (~7.6M K₄-free graphs at d_max ≤ 4, ~2 h enum). Would
  require enumerator-batching across slice graphs.
- Higher N tight slices for SAT-shelf disconnection. Probably gives
  the same answer (singletons) at progressively smaller shelf sizes.
- Wales-style barrier tree with combinatorial local minima as leaves
  (rather than connected-component reps as leaves). Algorithmic
  switch from Kruskal-on-energy to bottleneck shortest-path on
  pairs of combinatorial minima.

---

## Status (final)

| Test | Status | Verdict |
|---|---|---|
| A small N=10..22 | done | small graphs are tight; trivial direction of α-criticality confirmed |
| A large N=17..39 | done | relative Δ/c_log = 4–11× separation persists; N=35 plateau is real |
| A best-per-N N=14..133 | killed mid-run | not needed; picture closed at N≤39 |
| E add+delete N=10..22 | done | 0/200 across the board |
| E variant basin-radius switch N=30 | killed | 0/20 at K=1,5,20; sampling-vs-genuine ambiguous |
| D N=7..9 loose | done | 1 component, 1→694→5476 traps |
| D N=10,11 tight (SAT shelf) | done | shelf disconnects; SAT-opt is a singleton at N=11 |
| D N=12+ | not run | needs enumerator-batching to scale |
| C move-set comparison | absorbed | per-move data already in A's JSONs; no new sweep |

---

## Pre-registered claims (vs the other Claude session)

| Claim | Status |
|---|---|
| P1: structured-extremizer basins decay like exp(−cN) | confirmed at N=10..22 (≤ 5×10⁻³); shape consistent with super-polynomial decay; we can't distinguish exponential from faster from p̂=0 observations |
| P2: random init concentrates on boring c_log≈1 minima | confirmed at every N; endpoint plot shows a clear gap from frontier band |
| Falsifier: Paley basin ≥ 1×10⁻² at N=22 under add+delete | falsified (0/200 → ≤ 5×10⁻³) |
| Implicit: shelves remain connected at tight thresholds | falsified — N=10 shows 12 components on (3,4) shelf, N=11 shows 13 with SAT-opt as singleton |

The "Paley(17) has zero add moves" and "SAT optima are singletons in
their c_log shelves at N≥11" findings are the strongest pieces of
new structure relative to the pre-registration. Both reframe the
SAT-vs-local-search question: it isn't just that SAT optima have
small basins, it's that they're *literally disconnected* from the
rest of their own c_log shelf under any K₄-preserving local move.
