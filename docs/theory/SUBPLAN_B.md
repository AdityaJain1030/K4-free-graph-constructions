# Sub-plan B: a local, rigorous lower bound on `c` for K₄-free graphs

Status: first-pass implementation. Pipeline works end-to-end, produces
rigorous numbers, and confirms the expected outcome: this specific
local method closes the gap partially at small `d` and **cannot**
close it for the target degrees (`d = 8`, where Paley P(17) lives).
Plots + CSVs in `results/subplan_b/`.

---

## 1. The problem in one paragraph

A K₄-free graph is a graph with no four mutually adjacent vertices.
Write `α(G)` for the size of its largest independent set, `d_max(G)`
for its max degree, `N(G)` for its vertex count, and

```
c(G) = α(G) · d_max(G) / (N(G) · ln d_max(G)).
```

The **open conjecture** (Ajtai-Komlós-Szemerédi-style) says `c(G) ≥ c*`
for all K₄-free `G` and some universal `c* > 0`. Shearer (1995) proved
a weaker bound where `ln d` gets replaced by `√ln d`, and nobody has
improved it in 30 years. Paley P(17) achieves `c = 0.6789` with `d = 8`;
that's the current benchmark "near-counterexample".

We want a rigorous **lower** bound on `c`. The construction side of the
repo searches for graphs that minimise `c`; this doc describes the
opposite direction.

---

## 2. The one identity that makes everything local

Fix `G` and a vertex `v`. Let `N[v] = {v} ∪ N(v)`. For **any** graph `H`
and `λ > 0`, define the **independence polynomial**

```
Z(H, λ) = Σ_{I independent in H} λ^|I|.
```

Z counts independent sets by size, weighted by a fugacity `λ`. The
**hard-core measure** at fugacity `λ` is the probability distribution
on independent sets given by `Pr[I] = λ^|I| / Z(G, λ)`.

Under this measure the marginal `ρ_v = Pr[v ∈ I]` equals

```
ρ_v(G, λ) = λ · Z(G ∖ N[v], λ) / Z(G, λ).
```

**Key local inequality.** For any partition `V(G) = A ⊔ B`,

```
Z(G, λ) ≤ Z(G[A], λ) · Z(G[B], λ).
```

*Proof.* Every independent set of `G` restricts to an independent
set of `G[A]` and one of `G[B]`; the converse fails exactly because
cut edges between `A` and `B` can kill joint independence.
So the inequality is a cardinality-weighted injection. ∎

Applying this with `A = N[v]`, `B = V ∖ N[v]`:

```
ρ_v(G, λ)  ≥  λ / Z(G[N[v]], λ)  =  λ / (λ + Z(T_v, λ))
```

where `T_v = G[N(v)]` is the **neighborhood subgraph**. For K₄-free
`G`, every `T_v` is **triangle-free** (a K₄ through `v` is exactly a
triangle inside `T_v`).

---

## 3. From the identity to a bound on α

Any probability distribution supported on independent sets satisfies

```
α(G) ≥ E[|I|] = Σ_v Pr[v ∈ I] = Σ_v ρ_v.
```

That's the "pick a random independent set, its size is at most α, but
its expectation is a valid lower bound" step. Combined with §2:

```
α(G) ≥ max_{λ > 0}  Σ_v  λ / (λ + Z(T_v, λ))
                 ≡  L_HC(G).
```

We also always have the classic **Caro-Wei** bound:

```
α(G) ≥ Σ_v 1 / (d_v + 1)  ≡  L_CW(G).
```

The combined rigorous local bound we use is `max(L_CW, L_HC)`.

**Crucially, this bound is local in `T_v`.** If two graphs have the same
multiset of neighborhood types, they get the same bound. So you never
need to compute α on big graphs; you only need `Z(T, λ)` for
triangle-free `T` on `d ≤ d_max` vertices, and there are only finitely
many such `T` up to isomorphism at each `d`.

---

## 4. The universal bound at fixed `d`

For a `d`-regular K₄-free graph `G`, each `T_v` is a triangle-free
graph on `d` vertices. Let `𝒯_d` be the set of (iso-classes of)
triangle-free graphs on `d` vertices. Then

```
α(G)/N  ≥  min_{T ∈ 𝒯_d}  λ / (λ + Z(T, λ))   for any λ > 0
       ≥  max_λ  min_T   λ / (λ + Z(T, λ))      ≡ ρ_min(d).
```

Define

```
c_bound(d) = ρ_min(d) · d / ln d
```

and this is a **rigorous lower bound on `c(G)` for every `d`-regular
K₄-free graph `G`, of any size**. Combine with Caro-Wei (`1/(d+1)`):

```
c_bound_total(d) = max(ρ_min(d), 1/(d+1)) · d / ln d.
```

### How we compute `ρ_min(d)`

1. `nauty geng -t d` enumerates every triangle-free graph on `d`
   vertices (flag `-t` = no triangles).
2. For each `T`, compute `Z(T, λ)` as an integer-coefficient polynomial
   via a recursive independent-set DFS (`independence_polynomial` in
   `scripts/run_subplan_b.py`).
3. Sweep λ on a geometric grid `[0.05, 200]`; at each λ take the
   minimum of `λ / (λ + Z(T, λ))` over `T ∈ 𝒯_d`; take the max over λ.

The size of `𝒯_d` grows fast: 2, 3, 7, 14, 38, 107, 410, 1897, 12172
for `d = 2, 3, …, 10` (OEIS A006785). `d = 10` runs in under a minute.

---

## 5. Numbers — the actual computed bound

`results/subplan_b/universal_by_d.csv`:

| d  | |𝒯_d| | ρ_HC   | ρ_CW   | c_bound |
|----|------:|-------:|-------:|--------:|
| 2  |     2 | 0.2000 | 0.3333 | **0.962** |
| 3  |     3 | 0.1290 | 0.2500 | **0.683** |
| 4  |     7 | 0.0954 | 0.2000 | 0.577   |
| 5  |    14 | 0.0757 | 0.1667 | 0.518   |
| 6  |    38 | 0.0628 | 0.1429 | 0.478   |
| 7  |   107 | 0.0536 | 0.1250 | 0.450   |
| 8  |   410 | 0.0468 | 0.1111 | **0.427**   |
| 9  |  1897 | 0.0415 | 0.1000 | 0.410   |
| 10 | 12172 | 0.0373 | 0.0909 | 0.395   |

- **At `d = 3`, `c_bound = 0.683 > 0.6789`.** This is a rigorous
  statement: **no 3-regular K₄-free graph** can beat Paley P(17).
  That's a small but genuine closure; any construction search
  restricted to 3-regular graphs is pointless.
- **At `d = 8`** (the Paley P(17) degree), the bound is `0.427`.
  Paley P(17) sits at `c = 0.679`. We have a `0.68 − 0.43 = 0.25`
  **gap**. This is the "Shearer-level" outcome the original plan
  predicted for a small-`m` flag-algebra analogue.
- At every `d`, **Caro-Wei beats local hard-core** in this regime.
  The clean `1/(d+1)` term dominates because the `Z(G) ≤ Z(A) · Z(B)`
  inequality is loose. Improving this is the next methodological step
  (see §8).

---

## 6. What the DB comparison shows

Per-graph bounds (full DB, 585 K₄-free graphs with exact α, N up to
127, `results/subplan_b/per_graph_bounds.csv`):

- **Tightness of L_HC** vs exact α: typically 20–40%. Weak.
- Tightness of Caro-Wei: 40–70%. Better, but still lossy.
- Paley P(17) (`n=17, d=8, α=3, c=0.679`): `L_HC = 0.97` (32% of α),
  `L_CW = 1.89` (63% of α). Caro-Wei gives a per-graph
  `c-bound = 0.427`.

Observed `min c_log` by `N` (see `results/subplan_b/c_vs_n.png`): the
only `N` at which the DB touches `0.679` are `N ∈ {17, 34, 51, 68, 85}`
— exactly the Paley P(17) and its balanced blowups. Nothing else in the
database dips below `0.70`.

---

## 7. Extrapolation

Fit `c_bound(d) = A / ln d` (the form dictated by theory — both
Caro-Wei and the hard-core lower bound decay this way):

```
A = 0.824    (least-squares, d = 3…9)
c_bound(d=20)  ≈ 0.275
c_bound(d=50)  ≈ 0.211
c_bound(d=100) ≈ 0.179
c_bound → 0   as d → ∞
```

So **this method gets strictly worse as `d` grows** and cannot be
pushed to any universal `c* > 0`. That's not surprising: local
inequalities cannot capture the global averaging that forces a
non-trivial `ln d / d` scaling for α/N. The flag-algebra SDP or the
full Davies-Jenssen-Perkins-Roberts occupancy analysis would.

Plot: `results/subplan_b/extrapolate.png`.

---

## 8. What this script does **not** do (and why)

- **Not an SDP.** The optimization is `max_λ min_T (...)`: one
  scalar variable `λ`, finite minimum over pre-enumerated types.
  No semidefinite cone. Flag-algebra SDP would optimize over a
  distribution across neighborhood types with cross-type consistency
  constraints — that's Step 2 of the original plan and is a
  considerably larger engineering effort.

- **Not flag algebra.** No rooted-flag gluing, no averaging
  identities beyond the single `α(G) ≥ E[|I|]` step. This is
  deliberately the "baseline local bound" so we see where flag
  algebra would have to improve us.

- **Not using SAT-exact α.** SAT gives α for one graph at a time, but
  the bound here universally-quantifies over all `G`, so SAT doesn't
  plug in at this layer. SAT-exact α *is* used for validating the
  tightness ratio on the DB graphs (the `alpha` column in
  `per_graph_bounds.csv`).

- **Not tight for non-regular G.** The universal `c_bound_total(d)`
  is stated for `d`-regular K₄-free `G`. For irregular `G` the local
  inequality still gives `α(G) ≥ Σ_v max(1/(d_v+1), λ/(λ + Z(T_v,λ)))`,
  which converts to a per-graph c-bound, but the universal "worst-case
  over all such G" needs care about the degree distribution.
  We report both: `c_bound_HC` per-graph (§6) and `c_bound_regular`
  per-d (§5).

---

## 9. What would actually close the gap

Four concrete moves, in increasing cost / payoff:

1. **Smarter partition inequality.** Replace `Z(G) ≤ Z(A)·Z(B)` with a
   correlation-aware bound, e.g., Shearer-type entropy or a Lovász
   local-lemma style weight. This is where the factor of `ln d / d`
   lives in the literature. Estimated gain: bound becomes ~e× tighter.

2. **Occupancy method proper (Davies-Jenssen-Perkins-Roberts).** For
   `d`-regular triangle-free graphs they get `α/N ≥ (1+o(1)) ln d / d`.
   The K₄-free adaptation is triangle-free-local, which is our setting.
   Estimated gain: matches the conjecture's asymptotic exponent;
   probably lands around `c ≥ 0.5` at `d = 8`.

3. **Flag-algebra SDP at `m = 6` or `7`.** Full Step 2 of the original
   plan. PSD-certified weights over rooted flags. Estimated gain:
   at `m = 8` with exact `α(H)` per flag (using our SAT infra),
   plausibly `c ≥ 0.55–0.65` at `d = 8`. Not close to `0.679`, but
   meaningfully better than the current local bound.

4. **Exact finite-N via SAT.** Sub-plan A. Push SAT-exact `min c(N)` to
   `N = 25, 28` and certify no graph below some `c*` exists for those
   `N`. This is a finite-range theorem, not an asymptotic one, but it
   rules out small counter-constructions.

The current pipeline is the cheapest one (#0, so to speak) that is
rigorous end-to-end. It establishes the floor that everything else has
to beat.

---

## 10. How to run

```bash
# Compute per-graph bounds + universal-d bound.
micromamba run -n k4free python scripts/run_subplan_b.py \
    --n-max 200 --d-enum-max 10

# Produce plots + extrapolation fit.
micromamba run -n k4free python scripts/plot_subplan_b.py
```

Outputs land in `results/subplan_b/`:

- `per_graph_bounds.csv` — one row per DB graph with L_CW, L_HC,
  optimal λ, tightness ratios, and the derived c-bound.
- `by_dmax.csv` — min observed c_log per `d_max`, bound statistics.
- `universal_by_d.csv` — rigorous `ρ_min(d)`, `c_bound(d)` for
  `d = 1…d_enum_max`.
- `tightness_scatter.png`, `c_vs_n.png`, `c_vs_d.png`,
  `extrapolate.png` — plots.
- `extrapolation_fit.txt` — fit coefficients and extrapolated values.

---

## 11. Rung 2 — the exact hard-core occupancy

The rung-0 bound uses the **local** inequality
`ρ_v(G,λ) ≥ λ / (λ + Z(T_v,λ))`, which only depends on the
neighborhood `T_v = G[N(v)]`. The true marginal is

```
ρ_v(G, λ) = λ · Z(G ∖ N[v], λ) / Z(G, λ)
```

which sees the whole graph. Summing over `v` gives the *exact*
hard-core expectation `E_μ[|I|](λ)`, and maxing over `λ` gives the
tightest lower bound on `α(G)` obtainable from the hard-core measure
at any finite fugacity.

### 11.1 Implementation

`scripts/run_rung2_exact_hardcore.py` computes `Z(G,λ)` and
`Z(G ∖ N[v],λ)` as **exact integer-coefficient polynomials** via
DFS-enumeration of independent sets, then evaluates them on a
400-point log-grid `λ ∈ [0.05, 200]`. Complexity is
`O(N · 2^N)` per graph, so we cap at `N ≤ 20` (147 DB graphs; 0.02 s
per graph).

Results in `rung2_per_graph.csv`, aggregated by `d_max` in
`rung2_by_dmax.csv`.

### 11.2 The headline result

`E_max(G) / α(G)` — how close the exact hard-core bound gets to
the true independence number — across all 147 DB graphs:

```
mean tightness = 99.64%
max  tightness = 99.83%   (tightest, essentially α itself)
min  tightness = 96.08%
```

In other words: **the hard-core measure already captures α(G) to
within 0.4% on average**. There is almost no slack to recover.

### 11.3 The ceiling this exposes

For Paley P(17): `N=17, α=3, d=8`, so `c_log = 3·8/(17·ln 8) =
0.6789`. Rung 2 gives `E_max = 2.995`, i.e. `c_bound_rung2 =
0.6778`. The hard-core method **matches Paley almost exactly.**

This is not a coincidence — it is a **fundamental ceiling**:

> Any method that bounds `α` via a hard-core-style single-fugacity
> argument (rung 0, rung 2, cavity/BP, tree recursion, …) cannot
> prove a universal `c* > 0.6789`, because Paley P(17) is itself
> a K₄-free graph on which `E_max ≈ α`.

Put another way: on Paley P(17), even if your bound were *infinitely*
tight, it would output `α(Paley) = 3`, and hence `c = 0.6789`.
Every hard-core derivation you could ever write down is dominated by
`α` itself, and `α(Paley) = 3` is already the record.

Plots: `rung2_tightness.png`, `rung2_c_vs_d.png`.

### 11.4 Per-`d_max` ceiling table

| `d_max` | n graphs | mean tightness | min `c_bound_rung2` | min actual `c_log` |
|---|---|---|---|---|
| 2 | 16 | 99.77% | 0.9602 | 0.9618 |
| 3 | 16 | 99.66% | 0.9080 | 0.9102 |
| 4 | 40 | 99.57% | 0.7201 | 0.7213 |
| 5 | 17 | 99.63% | 0.7748 | 0.7767 |
| 6 | 30 | 99.62% | 0.7036 | 0.7050 |
| 7 | 16 | 99.65% | 0.7180 | 0.7195 |
| 8 | 12 | 99.69% | **0.6778** | **0.6789** |

The `min c_bound_rung2` column is always strictly less than the
true `min c_log`, i.e. rigorous, but within 0.15% at the critical
`d=8` row.

---

## 12. Rung 3 — Lovász θ and the SDP-upper-bound story

Rung 3 was planned as a **flag-algebra SDP** for a universal lower
bound; what I actually built is the **Lovász θ SDP**, which gives a
per-graph *upper* bound `α(G) ≤ θ(G)`.

### 12.1 Why this is still useful

`θ(G)` is computed as an SDP:

```
maximise  ⟨J, X⟩
s.t.      X ⪰ 0,  tr(X) = 1,
          X_ij = 0  for ij ∈ E(G).
```

It is the tightest SDP upper bound on `α` you get from a single
PSD matrix of order `N`. For vertex-transitive graphs,
`θ(G)·θ(Ḡ) = N`, so `θ(Paley_q) = √q` exactly.

What it tells us about *our* problem: **any SDP-relaxation-of-α
method has `α ≤ θ` built in.** So even if we found an SDP-certified
lower bound on `α` (e.g. via a dual argument, or a flag-algebra SDP
that *lower-bounds* α), it would still collide with the *inverse*
direction — the θ gap bounds how far SDP can reach at all.

### 12.2 Implementation

`scripts/run_rung3_lovasz_theta.py` uses cvxpy + SCS. Running over
all 147 K₄-free DB graphs with `N ≤ 20` takes ~3 s total.

Output: `rung3_theta.csv`.

### 12.3 Results

```
θ(G) / α(G):   min = 1.0000
               mean = 1.1234
               max  = 1.3744          (attained by Paley P(17))

θ(Paley P17) = 4.1231 = √17            (matches theory exactly)
```

Most DB graphs are θ-perfect or nearly so. Paley P(17) is again the
extremal case: θ over-estimates α by 37.4%. This is a well-known
"SDP gap": the θ bound is `√17 ≈ 4.12` while the truth is `α = 3`.

### 12.4 The big picture that Rung 3 reveals

Rewriting `c_bound` in terms of θ rather than α:

```
c_θ(Paley P17) = √17 · 8 / (17 · ln 8) = 0.9332.
```

So the best an SDP-upper-bound method can *say about Paley* is
`c(Paley) ≤ 0.9332`. The truth is `c(Paley) = 0.6789`. The SDP
is loose *upward* here, not downward. For our **lower** bound
question this means: the SDP/θ apparatus does not directly
help, but it rules out a very clean flag-algebra path — the
"SDP certificate of α ≥ f(n,d)" avenue has a baked-in ceiling
given by *θ* of the extremal graph, not *α*.

Plots:

- `rung3_theta_gap.png`: θ/α scatter, Paley highlighted.
- `rung3_c_vs_d.png`: θ-derived `c` vs actual `c` per `d_max`.
- `rung_all_compare.png`: rungs 0 (universal LB), 2 (exact HC LB
  in DB), 3 (θ UB), and actual, side by side.

---

## 13. Consolidated honesty

Summarising the four rungs:

| rung | what it bounds | direction | universal? | attained value at `d=8` |
|---|---|---|---|---|
| 0 | `α/N` via local HC | lower | **yes** | `c_univ(8) = 0.448` |
| 2 | `α/N` via exact HC | lower | per-graph | min in DB `= 0.678` |
| 3 | `α/N` via Lovász θ | upper | per-graph | `c_θ(Paley) = 0.933` |
| — | actual `c(G)` | exact | per-graph | `c(Paley) = 0.6789` |

The *only* rigorous universal lower bound we have produced is the
rung-0 one, which decays as `1/ln d` and gives `0.45` at `d=8`.
Rungs 2 and 3 are per-graph diagnostics that establish a **hard
ceiling**: no hard-core method can exceed α (rung 2), and no
SDP-relaxation-of-α method can beat θ at the worst graph (rung 3).

To break past `0.68` universally, the **flag-algebra SDP** at `m=6,7`
remains the only plausible next step — and it must operate on the
*distribution* over rooted flags, not on a single PSD matrix.
That's genuinely a multi-week research-code effort; it is not
encoded in this script.

### Commands to reproduce §§11–12

```bash
# Rung 2: exact hard-core per-graph (≤ 30 s total)
micromamba run -n k4free python scripts/run_rung2_exact_hardcore.py --n-max 20
micromamba run -n k4free python scripts/plot_rung2.py

# Rung 3: Lovász θ per-graph (≤ 10 s total)
micromamba run -n k4free python scripts/run_rung3_lovasz_theta.py --n-max 20
micromamba run -n k4free python scripts/plot_rung3.py
```

Typical runtime: ~30 s at `d_enum_max=9`, ~1 min at `d_enum_max=10`.
