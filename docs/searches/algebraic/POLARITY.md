# `PolaritySearch` — Erdős–Rényi polarity graph ER(q)

## What it does

For a prime power `q`, the projective plane PG(2, q) has
`q² + q + 1` points. The polarity graph ER(q) takes those points
as vertices with edges

> p ~ p'  iff  p · p' = 0  in F_q  and  p ≠ p'

where `p · p'` is the standard bilinear form.

ER(q) is **C₄-free**, hence K₄-free. It is `(q+1)`-regular except on
the `q+1` absolute points (`p · p = 0`), which sit at degree `q`
after the self-loops are dropped. `α ≈ q^{3/2}` asymptotically.

## Eligible N

| q  | N = q² + q + 1 |
|----|----------------|
| 2  | 7              |
| 3  | 13             |
| 5  | 31             |
| 7  | 57             |
| 11 | 133            |
| 13 | 183            |

Prime powers other than primes (`q = 4, 8, 9, 16, …`) are skipped —
the construction requires GF(q) arithmetic for non-prime q and we
haven't pulled in `galois` for that. The prime slice alone gives
N ∈ {7, 13, 31, 57, 133, 183} which is already plenty of coverage
beyond the circulant n ≤ 35 frontier.

## Why it exists

Circulants plateau at `c ≈ 0.94`. Polarity graphs hit a different
part of the parameter space — different (N, d, α) triples than
circulants / Cayley residues at comparable N — and give the
"algebraic ceiling" data point at N = 31, 57, 133, 183 that the
landscape study needs.

## Constructor

No kwargs beyond the base triad. Call with the target N; if N
isn't of the form `q² + q + 1` with q prime, `_run()` logs a
`skip` and returns `[]`.

## When to reach for it

- Computing the algebraic-family envelope at N = 31, 57, 133, 183.
- Providing large-N structured seeds for downstream polish.

## When **not** to reach for it

- You want a competitive finished product at Paley-17 scale —
  ER(q) is C₄-free which forces low density, so α isn't as small as
  a denser K₄-free graph could make it.
- N is not of the form `q² + q + 1` — the search is a no-op.
