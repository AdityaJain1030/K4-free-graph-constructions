# `CayleyResidueSearch` — intuition, caveats, scope

## What this search builds

For a prime `p` and an integer `k ≥ 2` with `p ≡ 1 (mod 2k)`, the `k`-th
power residues `R_k ⊂ Z_p^*` form a multiplicative subgroup of order
`(p-1)/k`. The Cayley graph `Cay(Z_p, R_k)` has vertex set `Z_p` and
edges `{i, i+s mod p}` for every `s ∈ R_k`. It is:

- **regular** of degree `(p-1)/k`,
- **vertex-transitive** (via translation) and **arc-transitive** (via
  multiplication by any element of `R_k`),
- circulant — so these graphs overlap with `CirculantSearch`'s output
  space. The difference is *which* connection sets get built.

The `p ≡ 1 (mod 2k)` condition ensures `-1 ∈ R_k`, which makes the
connection set symmetric (`S = -S`), so the Cayley graph is
undirected. The three small cases:

| `k` | Condition       | What you get                                       |
|-----|-----------------|----------------------------------------------------|
| 2   | `p ≡ 1 (mod 4)` | Paley graph `P(p)`                                 |
| 3   | `p ≡ 1 (mod 6)` | Cubic-residue Cayley graph                         |
| 6   | `p ≡ 1 (mod 12)`| Sextic-residue Cayley graph                        |

## Why this search exists alongside `CirculantSearch`

For `n ≤ 35`, `CirculantSearch` enumerates **every** connection set
exhaustively, so every residue-Cayley graph on `Z_p` with `p ≤ 35` is
already hit — this search produces no new graphs, only re-labels
existing ones with algebraic metadata (`prime`, `residue_index`,
`connection_set`) useful for the visualizer.

For `n ≥ 40`, exhaustive circulant enumeration is infeasible (see
`CIRCULANTS.md` caveat 1 and open question 3). Residue families give
a principled, O(1)-per-prime way to produce candidates at larger `n`,
without falling into the random-sampling trap.

## What the spectrum looks like (and why it's not strongly regular)

`Cay(Z_p, R_k)` has **exactly `k + 1` distinct eigenvalues**: the
trivial degree `(p-1)/k`, plus `k` Gauss-period eigenvalues (one per
coset of `R_k` in `Z_p^*`). So:

- `k = 2` → 3 eigenvalues → strongly regular graph (Paley).
- `k = 3` → 4 eigenvalues → **not** srg; it's a 3-class symmetric
  association scheme. If a downstream tool labels `Cay(Z_{19}, R_3)`
  as srg, that's wrong — it's one association-scheme class looser.
- `k = 6` → 7 eigenvalues → 6-class scheme.

This matters for the spectral bounds: Hoffman gives
`α ≤ N · (-λ_min) / (d - λ_min)`, and for `k = 3` at `p = 19` the
min eigenvalue is the smallest cubic Gauss period (≈ `-2.28`), which
yields `α ≤ ~5.2` → actual `α = 4`.

## What the search does

`CayleyResidueSearch(n=p, residue_indices=(2, 3, 6))` skips `n` that
isn't a prime ≥ 5, then for each `k` tries to build `Cay(Z_p, R_k)`
when `p ≡ 1 (mod 2k)`. K₄-free survivors are returned; the base class
scores by `c_log` and keeps `top_k`. A typical run across `p ∈
[5, 200]` produces ~50 graphs in a few seconds (most cost is the α
computation, not graph construction).

Metadata attached to each graph: `{"prime": p, "residue_index": k,
"connection_set": S}`.

## Caveats — read before scaling up

### 1. Asymptotic `c` growth is likely

Hoffman + the fact that non-trivial Gauss periods have magnitude
`Θ(√p)` predicts `c ≲ √p / ln(p/k)`. Whether `c` actually grows that
fast depends on how slack the Hoffman bound is for a given `(p, k)` —
and that's an empirical question for the range the repo cares about
(`n ≤ ~100`). Don't expect this family to beat `P(17)`; expect it to
*compete* with `P(17)` and provide structured benchmarks at primes
where `CirculantSearch` can't run.

### 2. Overlap with Paley enumeration

`k = 2` reproduces what `SAT_old/paley_enumeration/circulant_explorer.py`
already generated, just wired into the current `Search` framework
instead of an ad-hoc CSV. The `graph_db` dedup key is `(graph_id,
source)`, so the same graph appears under both `source='circulant'` /
`'cayley'` as expected — not a bug.

### 3. Primes only

The `p ≡ 1 (mod 2k)` condition requires `p` prime. For composite `n`
with a nice ring structure (e.g. `Z_{pq}`, `Z_{p^2}`), the character
theory gets harder — handle those in a future `MultiplicativeCoverSearch`
rather than widening this one.

### 4. No voltage covers

C(38; {2, 14, 16}) and C(34; {2, 4, 8, 16}) are trivial doubles (disjoint
copies) of their `Z_{19}` and `Z_{17}` bases — preserving `c` but not
producing new constructions. **Non-trivial connected covers** are not
in scope for this search; they need an independent `CoverSearch`
subclass.

## When to reach for it

- You want algebraically-labelled versions of small `p` Cayley graphs
  in the visualizer.
- You want to scan `p ∈ [40, 200]` where `CirculantSearch` can't go.
- You're testing a conjecture about the `c` curve across a residue
  family.

## When **not** to reach for it

- `n ≤ 35` with no interest in algebraic metadata — `CirculantSearch`
  already covers the same ground.
- Composite `n` — not supported.
- You want irregular / near-regular constructions — the whole family
  is exactly regular of degree `(p-1)/k`.
