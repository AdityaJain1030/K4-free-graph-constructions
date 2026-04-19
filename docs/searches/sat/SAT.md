# SAT — theoretical foundations

What the CP-SAT pipeline is actually solving and why the encoding is
sound. `SAT_EXACT.md` covers *how* the pipeline is built;
`SAT_OPTIMIZATION.md` covers *why each optimization helps*; this file
covers *what problem we're solving in the first place*.

---

## The conjecture

For K₄-free graphs `G` on `n` vertices with maximum degree `d`:

$$\alpha(G) \geq c \cdot \frac{n \log d}{d}$$

Best known: Shearer 1995, `α(G) ≥ c₁ · (n/d) · √(log d)`. The
conjecture asks whether the exponent on `log d` can be pushed from
`1/2` up to `1`.

Reformulated in the repo's preferred scoring,

$$c(G) = \frac{\alpha(G) \cdot d_{\max}(G)}{n \cdot \ln d_{\max}(G)}$$

the conjecture is: `inf c(G)` over K₄-free `G` is bounded away from
zero. Lowering `c` is how we probe the conjecture computationally —
every witness we find is a direct upper bound on `inf c`.

---

## Result 1 (EMPIRICAL, NOT PROVED): optimal α is the Ramsey value

**Claim.** For fixed `N`, the K₄-free graph minimising `c = αd/(N log d)`
has `α` as small as possible — i.e. the Ramsey value.

**Status.** Verified by SAT experiments up to `N = 22`. All optimal
graphs found have `α = R(4, t) - 1`-style Ramsey values. Multiple
proof attempts failed; it remains an empirical observation.

### Why the obvious proofs fail

- **Caro-Wei monotonicity.** `d ≥ N/α` gives `c ≥ 1/log(N/α)`, which is
  increasing in `α`. But this only bounds the *floor* — the actual
  `c` can sit far above the floor at small `α` and close to it at
  large `α`. A rising floor does not imply a rising function.

- **Sandwich with upper bounds.** Combine Caro-Wei (`d ≥ N/α`) with
  Neighborhood Ramsey (`d ≤ R(3, α+1) − 1`). Concrete test at
  `N=35`: worst `c` at `α=4` with `d=13` gives `0.579`; best `c` at
  `α=5` with `d=7` gives `0.514`. Sandwich doesn't rule out larger
  `α` winning. The gap `√log(N/α)` is exactly the open problem's
  width.

- **Shearer sandwich.** Tighter Shearer lower bound + Neighborhood
  Ramsey upper bound. Fails because the lower bound depends on `N`
  and the upper bound doesn't; they don't interlock tightly enough.

- **Assume the conjecture (circular, but informative).** If `α ≥
  c₀·(N log d)/d` holds, then `d ≥ c₀·(N/α)·log(N/α)` and the
  sandwich pins `d` to within a constant factor. Result:
  `c(α) ≈ c₀ · 1/(1 + log log λ / log λ)` where `λ = N/α` — essentially
  constant across `α`, with tiny log-log corrections.

### What Result 1's status tells us

Three regimes:

1. **If the conjecture is true (β = 1).** `c` is approximately
   constant across `α`. Which `α` you target is irrelevant. Result 1
   becomes vacuous.
2. **If the conjecture is false (β < 1).** `c` varies meaningfully
   across `α`. The empirical observation that Ramsey `α` is optimal
   becomes important, but we cannot prove it analytically — the tools
   to pin `d_min` are equivalent to resolving the conjecture.
3. **For computation regardless of β.** The empirical observation
   guides SAT search. Even without a proof, targeting Ramsey `α` is
   the best available heuristic, supported by all data up to `N=22`.

---

## Result 2 (PROVED): the optimal graph is near-regular

**Claim.** For any fixed `N` and `α`, the K₄-free graph minimising
`c` satisfies `d_max ≤ d_min + 1`.

**Proof.** An optimal graph must be α-critical: if any edge `e` could
be removed without increasing `α`, then `G − e` is K₄-free with the
same `α` but fewer edges, so `d_max(G − e) ≤ d_max(G)` and
`c(G − e) ≤ c(G)` — contradiction.

Hajnal's theorem (Lovász–Plummer, *Matching Theory* 1986, Ch. 12)
says every α-critical graph satisfies `d_max ≤ d_min + 1`. Original
α-critical theory: Zykov (1949).

---

## Result 3 (PROVED): minimising `c` ⇔ minimising `|E|`

**Claim.** Among K₄-free graphs on `N` vertices with `α = t−1`,
minimising `c` is equivalent to minimising `|E|`.

**Proof.**

*Forward.* By Result 2 the optimum is near-regular, so
`d_max ≈ 2|E|/N`. Since `d/log d` is monotone increasing for `d > e`,
minimising `d_max` minimises `c`. For near-regular graphs, minimising
`d_max` is equivalent to minimising `|E|`.

*Converse.* The `|E|`-minimiser subject to K₄-free and `α ≤ t−1` is
α-critical (else remove an edge), hence near-regular by Hajnal. So no
regularity or degree constraints are needed in the optimisation.

**Consequence for the solver.** The SAT model needs only

$$\min \sum_{i<j} x_{ij} \quad \text{s.t. K₄-free, } \alpha \leq t-1$$

No symmetry breaking, no degree bounds, no regularity enforcement.
The solution is automatically α-critical and near-regular. This is
the justification for the encoding in `search/sat_exact.py`.

---

## The sandwich: bounding `d_min(N, α)`

For a K₄-free near-regular graph on `N` vertices with `α(G) = α`:

### Lower bound 1 — Caro-Wei

`α ≥ Σ_v 1/(d(v)+1)`, so for near-regular degree `d`:

$$d \geq \frac{N}{\alpha} - 1 \approx \frac{N}{\alpha}$$

### Lower bound 2 — Shearer 1995 (strictly stronger)

$$\alpha(G) \geq c_1 \cdot \frac{N}{d} \cdot \sqrt{\log d}$$

Solving self-referentially with `d = (N/α) · f`:

$$d \geq \frac{c_1 N}{\alpha} \cdot \sqrt{\log \frac{N}{\alpha}}$$

Stronger than Caro-Wei by `√log(N/α)`. Reference: Shearer, *Random
Structures & Algorithms* 7 (1995) 269–271 — recursive application of
the 1983 triangle-free bound to (triangle-free) neighborhoods of a
K₄-free graph.

### Upper bound — Neighborhood Ramsey

In a K₄-free graph, every `N(v)` is triangle-free on `d` vertices. An
independent set in `N(v)` is independent in `G`. So if
`d ≥ R(3, α+1)` the neighborhood contains an independent `(α+1)`-set,
contradiction. Therefore:

$$d \leq R(3, \alpha+1) - 1 = O\!\left(\frac{\alpha^2}{\log \alpha}\right)$$

Small exact values:

| α | `d ≤ R(3, α+1) − 1` |
|---|---|
| 3 | 8  |
| 4 | 13 |
| 5 | 17 |
| 6 | 22 |

### The β parametrisation

Write `d_min(N, α) = (N/α) · (log(N/α))^β`. Then:

- Shearer → `β ≥ 1/2` (proved)
- Conjecture → `β = 1` (open)
- Neighborhood Ramsey → `β ≤ 1` at `N` near `R(4,t) − 1`

So `β ∈ [1/2, 1]`. The conjecture is *equivalent* to `β = 1`.

---

## Result 4 (PROVED): conjecture ⇔ `β = 1`

By Results 2–3, `c_min = (t−1)·d_min / (N · log d_min)`. Substitute
`d_min = (N/(t−1)) · (log λ)^β` with `λ = N/(t−1)`:

$$c_{\min} \approx \frac{(\log \lambda)^\beta}{\log \lambda} = (\log \lambda)^{\beta - 1}$$

This tends to zero iff `β < 1`, and stays constant iff `β = 1`.

So the computational observable — does `inf c` stay bounded away from
zero as `N` grows? — directly measures `β`. Each new low-`c` witness
tightens the empirical picture.

*Note.* Not equivalent to the `R(4,t)` gap or the Erdős-Rogers
problem; those are thematically related but logically distinct.

---

## Result 5 (PROVED): clean computational formulation

For each `N` and target `α = t−1`:

> Minimise `Σ_{i<j} x_{ij}`
> Subject to:
> - **K₄-free**: for every 4-clique `{a,b,c,d}`,
>   `x_ab + x_ac + x_ad + x_bc + x_bd + x_cd ≤ 5`
> - **α ≤ t−1**: for every `t`-subset `S`, at least one edge inside
>   `S` is present

The solution is automatically α-critical (hence near-regular) by
Results 2–3. `d_min(N) = 2|E*|/N` directly measures β.

This is what `search/sat_exact.py:_build_model` encodes, one `(α, d)`
box at a time. The scan in §2 of `SAT_EXACT.md` walks the Pareto
frontier of `(α, d)` pairs; `prove_box` and `verify_optimality` close
the remaining boxes to produce certified optimal `c_log` per `N`.

---

## Empirical baseline (verified optimal for N ≤ 22)

Reproduced from the original unconstrained CP-SAT scan
(`reference/pareto/`). All optimal graphs are regular;
`α` matches the Ramsey prediction.

| N  | d | α | c = αd/(N·ln d) | d/(N/α) |
|----|---|---|-----------------|---------|
| 12 | 5 | 3 | 0.777 | 1.25 |
| 13 | 6 | 3 | 0.773 | 1.38 |
| 14 | 6 | 3 | 0.718 | 1.29 |
| 15 | 7 | 3 | 0.719 | 1.40 |
| 16 | 8 | 3 | 0.721 | 1.50 |
| 17 | 8 | 3 | 0.679 | 1.41 |
| 18 | 6 | 4 | 0.744 | 1.33 |
| 19 | 6 | 4 | 0.705 | 1.26 |
| 20 | 7 | 4 | 0.719 | 1.40 |
| 21 | 8 | 4 | 0.733 | 1.52 |
| 22 | 9 | 4 | 0.745 | 1.64 |

`c` fluctuates around `0.7` and does not trend toward zero —
consistent with `β` near `1` (conjecture true). But `t ∈ {4, 5}` is
too small to distinguish `β = 1/2` from `β = 1` through log factors
alone; this is why pushing `N` higher on the cluster matters.

Current pipeline (`sat_exact` + warm starts + `prove_box`) has in
several cases beaten the N≤22 numbers above at larger N; see
`graph_db` for the live frontier.

---

## What remains open

1. **Result 1** — does optimal `α` equal the Ramsey value?
   Empirically supported, analytically unresolved.
2. **Optimal N within a Ramsey window** — which `N ∈
   [R(4,t−1), R(4,t)−1]` minimises `c`? No analytical tool resolves
   this.
3. **The value of β** — the central open question. Equivalent to the
   conjecture. Needs either new theory or empirical measurement at
   larger `t` (`t ≥ 7`) where the logarithmic factors become
   distinguishable.

The whole SAT pipeline exists to push (3) — each certified-optimal
`c_min(N)` at larger `N` is a data point on `(log λ)^{β-1}`.
