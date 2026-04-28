# Erdős–Rényi polarity graph `ER(q)`

For a prime power `q`, the projective plane `PG(2, q)` has `q² + q + 1`
points. Fix the standard symmetric bilinear form `(x, y) ↦ x_0 y_0 +
x_1 y_1 + x_2 y_2` over F_q. The orthogonal-polarity graph `ER(q)`
takes the projective points as vertices with edges

> `p ~ p'` iff `p · p' = 0` in F_q and `p ≠ p'`.

`ER(q)` is **C₄-free** (any two distinct lines meet in exactly one point,
so any two points have at most one common neighbour) and therefore
K₄-free. It is `(q+1)`-regular except on the `q + 1` **absolute points**
(`p · p = 0`) which lose the self-loop and end up at degree `q` after
the loops are dropped.

> Implemented at
> [`search/algebraic_explicit/polarity.py`](../../search/algebraic_explicit/polarity.py).
> Field arithmetic from
> [`utils/algebra.py`](../../utils/algebra.py) — handles both prime q
> and tabled prime-power q ∈ {4, 8, 9, 16, 25, 27, 32}. Ingested under
> `source="polarity"`; results in
> [`graphs/polarity.json`](../../graphs/polarity.json).

---

## Why ER(q) is C₄-free (and hence K₄-free)

A `C_4` in `ER(q)` would be four projective points `p_1, p_2, p_3, p_4`
with `p_1 ⊥ p_2`, `p_2 ⊥ p_3`, `p_3 ⊥ p_4`, `p_4 ⊥ p_1` and the diagonals
non-orthogonal. The pair `(p_1, p_3)` has two common neighbours
`p_2` and `p_4`. But two projective points determine a unique projective
line, and the polarity sends a point to its polar line — so the points
orthogonal to both `p_1` and `p_3` form a single line, intersected with
the points (which is at most a line). Two distinct projective lines meet
in at most one point. Hence at most one common neighbour, and no `C_4`.

`K_4`-freeness follows because every `K_4` contains a `C_4`.

## Eligible N (now covering prime-power q)

| q | N = q² + q + 1 | source |
|---:|---:|---|
| 2 | 7 | prime |
| 3 | 13 | prime |
| 4 | 21 | F_4, x² + x + 1 |
| 5 | 31 | prime |
| 7 | 57 | prime |
| 8 | 73 | F_8, x³ + x + 1 |
| 9 | 91 | F_9, x² + 1 |
| 11 | 133 | prime |
| 13 | 183 | prime |
| 16 | 273 | F_{16}, x⁴ + x + 1 |
| 17 | 307 | prime |
| 19 | 381 | prime |
| 23 | 553 | prime |

Prime-power q is supported via `utils.algebra.field`, which has
hand-tabled irreducibles for q ∈ {4, 8, 9, 16, 25, 27, 32}. Adding more
prime powers is a one-line append to `_PRIME_POWER_IRREDUCIBLES`.

## Spectrum and α

`ER(q)` is **not** vertex-transitive (the absolute points break
transitivity), but it has a clean spectrum:

- One trivial eigenvalue `λ_0 = q + 1` (corresponding to the
  all-ones vector — but only approximately, since the absolute points
  have lower degree).
- `q² + q` non-trivial eigenvalues each equal to `±√q` (Hermitian
  curve / unital structure, see e.g.
  [Bachoc–Pasini–Tonchev 2003] for the formal eigenspace
  decomposition).

Hoffman bound: with `λ_min = -√q` and `d ≈ q + 1`,
`α(ER(q)) ≤ N · √q / (q + 1 + √q) ≈ q^{3/2}` for large q. Empirically
α tracks this closely:

| q | n | α | α / N | d_max | c_log |
|---:|---:|---:|---:|---:|---:|
| 2 | 7 | 3 | 0.428 | 3 | 1.170308 |
| 3 | 13 | 5 | 0.385 | 4 | 1.109765 |
| 4 | 21 | 7 | 0.333 | 5 | 1.035558 |
| 5 | 31 | 10 | 0.323 | 6 | 1.080214 |
| 7 | 57 | 15 | 0.263 | 8 | 1.012418 |
| 8 | 73 | 17 | 0.233 | 9 | **0.953881** |
| 9 | 91 | 22 | 0.242 | 10 | 1.049943 |
| 11 | 133 | 29 | 0.218 | 12 | 1.052974 |
| 13 | 183 | 38 | 0.208 | 14 | 1.101569 |
| 16 | 273 | 49 | 0.180 | 17 | 1.076969 |
| 17 | 307 | 55 | 0.179 | 18 | 1.115689 |
| 19 | 381 | 62 | 0.163 | 20 | 1.086410 |
| 23 | 553 | 84 | 0.152 | 24 | 1.147108 |

## Why c_log doesn't beat P(17)

The asymptotic ratio:

```
c_log(ER(q)) ≈ (q^{3/2}) · (q + 1) / ((q² + q + 1) · ln(q + 1))
            ≈ q^{1/2} · (1 + O(1/q)) / ln q  ⟶ ∞
```

So c_log of the polarity family **grows** like `√q / ln q`.

But the empirical curve plateaus around 1.0 because:
- α is *slightly* below the Hoffman bound (q^{3/2} factor saturated to
  Hoffman, not the bare bound),
- d_max is exactly q + 1 (no slack),
- the (q+1) factor and the q^{3/2} factor combine before the ln(q+1)
  denominator kicks in.

Best is `ER(8)` at c_log = 0.954 — the q² spectrum + the prime-power
q = 8 hit a sweet spot. None of the family beat the Paley P(17)'s
0.679. The C₄-freeness is too restrictive: forbidding C_4 forces
`m = O(N^{3/2})`, so density is asymptotically lower than what a
generic K₄-free graph can support, which means α is forced higher.

## Relationship to other algebraic constructions

- **Norm graph** = `Cay(Z_{q²−1}, K)` where K is the norm-1 subgroup
  image — defined on q² − 1 vertices vs polarity's q² + q + 1, and
  a circulant rather than non-VT. **K₄-free only at q = 2.** See
  [`NORM_GRAPH.md`](NORM_GRAPH.md).
- **Power-residue Cayley** `Cay(Z_p, R_k)` — defined on q vertices,
  arc-transitive, more competitive c_log. See [`CAYLEY.md`](CAYLEY.md).
- **Mattheus–Verstraete** `Hq*` — uses the Hermitian unital of
  `PG(2, q²)` (related projective-plane construction over the
  square-extension field). See [`MATTHEUS_VERSTRAETE.md`](MATTHEUS_VERSTRAETE.md).

## When to reach for it

- You want a non-vertex-transitive K₄-free benchmark at large N
  (q ≥ 7 gives N ≥ 57, beyond the circulant n ≤ 35 frontier).
- You want a deterministic algebraic graph with a clean Hermitian
  spectrum.
- You want an algebraic-ceiling reference at exactly N = q² + q + 1.

## When **not** to reach for it

- You want competitive c_log — the family plateaus around 1.0, well
  above the P(17) frontier of 0.679.
- N is not of the form q² + q + 1 — the search is a no-op.
- You want a vertex-transitive graph — the absolute points break
  transitivity. Use `CAYLEY.md` instead.

## Related

- [`MATTHEUS_VERSTRAETE.md`](MATTHEUS_VERSTRAETE.md) — uses the same
  underlying projective-plane construction but over `F_{q²}` for the
  asymptotic Ramsey lower bound.
- [`NORM_GRAPH.md`](NORM_GRAPH.md) — different algebraic construction
  on `q² − 1` vertices, K₄-free only at q = 2 (negative result).
- [`BEYOND_CAYLEY.md`](BEYOND_CAYLEY.md) §2 — places polarity on the
  α/θ tightness map. Polarity sits *below* the θ-tight surface (since
  it is non-VT), making it a candidate for "cheap α improvements" via
  edge-switching.
