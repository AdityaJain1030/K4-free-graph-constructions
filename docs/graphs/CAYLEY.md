# Power-residue Cayley `Cay(Z_p, R_k)` (a.k.a. `PrimeCirculantSearch`)

For a prime `p` and an integer `k ≥ 2` with `p ≡ 1 (mod 2k)`, the
`k`-th power residues `R_k = {x^k mod p : x ∈ Z_p^*} ⊂ Z_p^*` form a
multiplicative subgroup of order `(p − 1)/k`. The Cayley graph
`Cay(Z_p, R_k)` has vertex set `Z_p` and edges
`{i, i + s mod p}` for every `s ∈ R_k`.

It is:

- **regular** of degree `(p − 1)/k`,
- **vertex-transitive** (translations act) and **arc-transitive**
  (multiplication by any `r ∈ R_k` permutes both vertices and edges),
- a **circulant** — so these graphs lie inside the connection-set space
  enumerated by `CirculantSearch`.

The `p ≡ 1 (mod 2k)` condition ensures `−1 ∈ R_k`, so `S = −S` and the
Cayley graph is undirected. The three small cases:

| `k` | Condition | Name |
|---|---|---|
| 2 | `p ≡ 1 (mod 4)` | **Paley graph** `P(p)` |
| 3 | `p ≡ 1 (mod 6)` | **Cubic-residue Cayley** |
| 6 | `p ≡ 1 (mod 12)` | **Sextic-residue Cayley** |

> Implemented at
> [`search/algebraic_explicit/prime_circulants.py`](../../search/algebraic_explicit/prime_circulants.py).
> Class is `PrimeCirculantSearch` (renamed from `CayleyResidueSearch`).
> Ingested under `source="cayley"` — shares `graphs/cayley.json` with
> historical residue-class results.

---

## Why this family contains the c_log frontier

The headline result for the entire repo:

> **The Paley graph `P(17)` (k=2, p=17) achieves c_log = 0.6789, the
> lowest c_log of any K₄-free graph in the database.**

P(17) sits below every other algebraic construction, every random
baseline, and every search-derived plateau. Beating it requires a
construction that is simultaneously:

1. K₄-free (Paley P(17) is the largest Paley graph that *is* K₄-free
   — Paley P(p) for `p ≥ 29 ≡ 1 (mod 4)` contains K_4).
2. Hoffman-saturated at α = (p − 1)/(k+1) or close to it.
3. With low enough `α · d_max / (N · ln d_max)` to clear 0.679.

Only Cayley graphs with carefully chosen non-power-residue connection
sets have come close (see `CAYLEY_TABU_GAP.md`), and none of them
beats P(17).

## Spectrum and Hoffman bound

`Cay(Z_p, R_k)` has **exactly `k + 1` distinct eigenvalues**: the
trivial degree `(p − 1)/k`, plus `k` Gauss-period eigenvalues (one per
coset of `R_k` in `Z_p^*`).

- `k = 2` → 3 eigenvalues → strongly regular graph (Paley).
  Spectrum `{(p−1)/2, ((-1 + √p)/2)^{((p−1)/2)}, ((-1 − √p)/2)^{((p−1)/2)}}`.
- `k = 3` → 4 eigenvalues → 3-class symmetric association scheme.
  Eigenvalues are cubic Gauss periods; not strongly regular.
- `k = 6` → 7 eigenvalues → 6-class scheme.

The Hoffman bound applied to Paley:
`α(P(p)) ≤ p · |λ_min| / (d − λ_min) = p · ((-1+√p)/2 + 1) / ((p-1)/2 - (-1-√p)/2 + ...) ≈ √p`.
For p = 17 this gives `α(P(17)) ≤ √17 ≈ 4.12`, but the actual
α(P(17)) = 3 — Hoffman has slack of ~1, which is the ratio that lets
P(17) be c_log-optimal.

For `k = 3, p = 19`: λ_min is the smallest cubic Gauss period
`(-1 + √(-3·19))/2 ≈ -2.28`. Hoffman gives
`α ≤ 19 · 2.28 / (6 + 2.28) ≈ 5.23`. Actual α = 4.

## When K₄-freeness holds (and when it doesn't)

| `k` | `p ≡ 1 (mod 2k)` smallest p | K₄-free? |
|---|---|---|
| 2 | 5 | ✓ |
| 2 | 13 | ✓ |
| 2 | 17 | **✓ (last K₄-free Paley)** |
| 2 | 29 | ✗ |
| 2 | 37 | ✗ |
| 3 | 7 | ✓ |
| 3 | 13 | ✓ |
| 3 | 19 | ✓ |
| 3 | 31, 37, 43, 61, 67, 79, 127 | ✓ |
| 6 | 13 | ✓ |
| 6 | 37 | ✓ |
| 6 | 61, 73, 97, 109 | ✓ |

**Paley graphs become non-K₄-free at p ≥ 29.** This is the structural
fact that bounds the c_log frontier: P(17) is the largest K₄-free Paley,
and Paley parameters are uniquely good for low c_log within the family.

Higher-k variants (cubic, sextic) stay K₄-free for many more primes,
but their density (= (p−1)/k) is lower, so α grows faster and c_log
doesn't reach as low as P(17). The full sweep results live in
[`experiments/algebraic_explicit/README.md`](../../experiments/algebraic_explicit/README.md).

## Empirical c_log table (best per (n, k))

From [`graphs/cayley.json`](../../graphs/cayley.json):

| n | k | name | c_log | α | d_max |
|---:|---:|---|---:|---:|---:|
| 17 | 2 | P(17) | **0.6789** | 3 | 8 |
| 19 | 3 | cubic | 0.7050 | 4 | 6 |
| 13 | 2 | P(13) | 0.7728 | 3 | 6 |
| 37 | 6 | sextic | 0.8145 | 9 | 6 |
| 31 | 3 | cubic | 0.8406 | 6 | 10 |
| 67 | 3 | cubic | 0.8498 | 8 | 22 |

Note the **non-monotonicity in k**: at p = 37, k = 6 (sextic) gives
c_log = 0.815, *better* than k = 3 (cubic) at 0.913. The "smaller k
is better" intuition is wrong; the k that minimises c_log depends on
how dense `R_k` is at the specific (p, λ_min) profile.

## Why the search exists alongside `CirculantSearch`

For `n ≤ 35`, `CirculantSearch` enumerates **every** connection set
exhaustively, so every residue-Cayley graph with `p ≤ 35` is already
hit — `PrimeCirculantSearch` produces no new graphs there, only
re-labels existing ones with algebraic metadata (`prime`,
`residue_index`, `connection_set`) useful for the visualiser.

For `n ≥ 40`, exhaustive circulant enumeration is infeasible (see
[`CIRCULANTS.md`](CIRCULANTS.md) caveat 1). Power-residue families give
a principled, O(1)-per-prime way to produce candidates at larger n,
without the random-sampling tax.

## Open questions

1. **k-sweep is incomplete.** Only `k ∈ {2, 3, 6}` are currently swept.
   Every divisor of `p − 1` gives an eligible k; e.g. p = 41 admits
   k ∈ {2, 4, 5, 8, 10, 20, 40}, of which only k = 2 has been tried
   (and gives a non-K₄-free graph). Extending the sweep to all
   divisors might find lower-c_log hits at large primes, especially
   for `k = 4, 5, 8`.
2. **No voltage covers.** `Cay(Z_2 × Z_p, S)` (a "double cover" of the
   Z_p Cayley) is an obvious extension to N = 2p; not yet implemented
   as a `Search` subclass. See [`CAYLEY_TABU.md`](CAYLEY_TABU.md) for
   the search-based approach to non-prime n.

## When to reach for it

- You want a labelled, algebraic version of a small-p Cayley graph with
  connection-set metadata in the visualiser.
- You want to scan `p ∈ [40, 500]` where `CirculantSearch` cannot.
- You're testing a conjecture about the c_log curve across a residue
  family.

## When **not** to reach for it

- `n ≤ 35` with no need for algebraic metadata — `CirculantSearch`
  already covers the same ground.
- Composite n — `p ≡ 1 (mod 2k)` requires p prime. See
  [`CAYLEY_TABU.md`](CAYLEY_TABU.md) for general non-prime n.
- You want irregular / near-regular constructions — the family is
  exactly regular of degree `(p − 1)/k`.

## Related

- [`CIRCULANTS.md`](CIRCULANTS.md) — exhaustive circulant enumeration,
  the immediate parent class.
- [`CAYLEY_TABU.md`](CAYLEY_TABU.md) — generic Cayley search; reaches
  non-prime n and non-cyclic groups.
- [`BEYOND_CAYLEY.md`](BEYOND_CAYLEY.md) — argues why Paley P(17) is
  unbeatable from the spectral side, and where to look for non-Cayley
  structural improvements.
- [`P17_LIFT_OPTIMALITY.md`](P17_LIFT_OPTIMALITY.md) — why P(17) is
  also unbeatable on the lift side.
