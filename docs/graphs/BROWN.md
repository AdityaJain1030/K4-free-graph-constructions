# Brown's C₄-free graph on `F_q³`

Brown (1966): for an odd prime `q ≥ 5`, the **unit-distance graph** on
the affine 3-space `F_q³` has

- vertices `F_q³` (so `|V| = q³`),
- edges
  `(x, y, z) ~ (x', y', z')`  iff
  `(x − x')² + (y − y')² + (z − z')² = 1` in `F_q`.

The graph is **C₄-free**: any two distinct points have at most two
common neighbours, because the intersection of two unit spheres in
`F_q³` is the intersection of two affine quadrics — generically a
conic in a plane, but the Cayley structure forces it to a 2-set or
empty. C₄-free implies **K₄-free** (any K_4 contains a C_4).

> Implemented at
> [`search/algebraic_explicit/brown.py`](../../search/algebraic_explicit/brown.py).
> Ingested under `source="brown"`.

---

## Why this construction matters historically

Brown's graph was the first explicit C₄-free graph reaching the
optimal `Θ(N^{3/2})` edge density (matching Reiman's earlier
upper bound). For decades it was the only general-q construction
attaining the C₄-free Turán density. The polarity graph
`ER(q)` (see [`POLARITY.md`](POLARITY.md)) gives a different optimal
construction at `N = q² + q + 1` rather than `N = q³`; Brown's graph
is the algebraic-ceiling probe at the much-larger `N = q³` slice.

It is also the basis of the lower bound `r(3, k) = Ω(k² / log² k)` —
Brown's graph realises this via the bipartite incidence-style structure
of unit-distance triples.

## Eligible N

| q | N = q³ |
|---:|---:|
| 5 | 125 |
| 7 | 343 |
| 11 | 1331 |
| 13 | 2197 |

q = 3 is technically defined but the sphere equation has too few
solutions for the graph to be informative (degree drops sharply, α
becomes trivial). Non-prime q would need a `GF(q)` extension (not yet
in `utils.algebra` for this construction's degree-3 form).

## Spectral and density profile

For odd prime `q ≥ 5`:

- |V| = q³.
- Average degree = (number of length-1 vectors in `F_q³`) ≈ q² (the
  unit-sphere `S^2 ⊂ F_q³` has `q² + O(q)` points by Hasse–Weil for
  generic q).
- Maximum degree ≈ q² as well (Brown's graph is *almost* regular but
  has mild degree variation at points lying on degenerate spheres).
- Spectrum: largest eigenvalue ≈ q²; non-trivial eigenvalues bounded
  by `2q` (Hasse–Weil-type). So Hoffman gives
  `α ≤ q³ · 2q / (q² + 2q) ≈ 2q² / (1 + 2/q)`.

Empirically (single instance in graph_db):

| n | q | α | d_max | c_log |
|---:|---:|---:|---:|---:|
| 125 | 5 | 20 | 30 | 1.4113 |

α = 20 is far below the Hoffman bound (≈ 38), so Brown's graph at
q = 5 is **not** Hoffman-saturated — it has slack on α. But the high
d_max (30) and the linear-in-N denominator combine to push c_log to
the 1.4 range.

## Why c_log doesn't beat the frontier

Asymptotic c_log:

```
c_log(Brown_q) = α · d_max / (N · ln d_max)
              ≈ 2 q² · q² / (q³ · ln q²)
              = 2q · (1 + o(1)) / ln q
```

So c_log **grows** with q at rate ≈ q / log q — Brown's graph is
*much worse* asymptotically than the C₄-free polarity graph (which
plateaus around 1.0 instead of growing). This is because Brown's
N = q³ is much larger than polarity's `q² + q + 1` for the same q,
so the same Hoffman α-bound — which scales like `q^{3/2}` for both —
gives a worse c_log on Brown by a factor of `q^{3/2}/(q+1)` ≈ `√q`.

## Cost notes

- Build cost is `O(|S| · q³)` with `|S| ≈ q²` (the number of length-1
  3-vectors), so `O(q⁵)` total work. At q = 13 that's ≈ 4 × 10⁵ edges
  visited — a few seconds.
- α computation at q = 7 (n = 343) is the bottleneck — CP-SAT can
  take minutes on a 343-vertex non-VT graph.

## When to reach for it

- You want an explicit construction at `N = q³` for the algebraic-ceiling
  envelope.
- You want to compare Hoffman saturation across the algebraic family
  (Brown is the cleanest example of an *under-saturated* algebraic
  K₄-free graph in the DB).
- You want a Ramsey-style construction (Brown gives the lower bound on
  `r(3, k)`).

## When **not** to reach for it

- Small N (< 100) — use circulant or SAT instead.
- You want a finished competitive c_log — Brown grows asymptotically.
- q is even or q = 3 — not supported by the current driver.

## Related

- [`POLARITY.md`](POLARITY.md) — the C₄-free polarity graph at
  `N = q² + q + 1`, much closer to competitive c_log.
- [`MATTHEUS_VERSTRAETE.md`](MATTHEUS_VERSTRAETE.md) — the modern
  Ramsey-lower-bound construction; supersedes Brown for `r(3, t)`-type
  and `r(4, t)`-type questions.
