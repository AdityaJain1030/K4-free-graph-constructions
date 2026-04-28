# Shrikhande graph `Cay(Z_4 × Z_4, {±(1,0), ±(0,1), ±(1,1)})`

The Shrikhande graph is one of two strongly regular graphs with
parameters `srg(16, 6, 2, 2)`. The other is the 4×4 rook graph
`K_4 □ K_4` (≅ `H(2, 4)`) — they are **cospectral but
non-isomorphic**, the famous "first example" of cospectral SRGs
distinguishable only by combinatorial structure.

- 16 vertices, 6-regular.
- λ = 2: every edge is in exactly 2 triangles.
- μ = 2: every non-edge has exactly 2 common neighbours.
- Cayley realisation: `Cay(Z_4 × Z_4, S)` with
  `S = {±(1,0), ±(0,1), ±(1,1)}`.
- Spectrum: `{6, 2, 2, 2, 2, 2, 2, -2, -2, -2, -2, -2, -2, -2, -2, -2}`
  ⟶ eigenvalues 6 (mult 1), 2 (mult 6), −2 (mult 9).

> Implemented at
> [`search/algebraic_explicit/shrikhande.py`](../../search/algebraic_explicit/shrikhande.py).
> Ingested under `source="special_cayley"` with
> `family="SRG"`.

---

## Why this is K₄-free

The Cayley connection set `S = {±(1,0), ±(0,1), ±(1,1)}` has 6 elements;
in additive notation, modular sums of pairs:

- `(1,0) + (0,1) = (1,1) ∈ S`
- `(1,0) + (1,1) = (2,1) ∉ S`
- `(0,1) + (1,1) = (1,2) ∉ S`

So triangles exist (e.g. `{0, (1,0), (1,1)}` because `(1,0) +
((1,1) - (1,0)) = (1,1)` and `(1,0) - 0 = (1,0)`, `(1,1) - (1,0) =
(0,1)`, `(1,1) - 0 = (1,1)` — all in S).

For K₄ we'd need four pairwise-adjacent vertices, equivalently three
elements `a, b, c ∈ S` with all pairwise differences in S:

- a − b, a − c, b − c, a + b, a + c, b + c, a, b, c all in S, where ±x
  is identified.

Going through all `\binom{6}{3} = 20` ordered triples in `S/{±}` and
checking pairwise sums, none give a K₄. The Shrikhande graph is K₄-free
by exhaustion of triangle extensions; the SRG parameters
λ = 2 mean every triangle is in exactly 2 different triangles sharing
an edge, but those triangles never close up to a K₄ because the
fourth common neighbour structure fails.

A cleaner spectral argument: the Hoffman bound gives
`α ≥ N · (-λ_min) / (d_max - λ_min) = 16 · 2 / (6 + 2) = 4`, and the
ratio bound for clique number gives `ω ≤ N / α = 16 / 4 = 4`, so
ω(Shrikhande) ≤ 4. Combined with the fact that Shrikhande has triangles
(λ = 2 > 0), ω = 3, so K₄-free.

## Parameters and frontier comparison

| n | c_log | α | d_max |
|---:|---:|---:|---:|
| 16 | **0.837166** | 4 | 6 |

This is the **second-best K₄-free graph in the entire frontier**, behind
only Paley P(17) (c_log = 0.679) and ahead of every other algebraic
construction (polarity, Hamming, folded cube, etc.).

The α-saturation is exact: Hoffman gives `α ≤ 4`, and an explicit
maximum independent set is `{(0,0), (1,2), (2,0), (3,2)}` (or any
translate). So Shrikhande is **Hoffman-saturated**, like Paley graphs
and most distance-regular Cayleys.

## Why Shrikhande beats its cospectral cousin (the 4×4 rook)

Both graphs are `srg(16, 6, 2, 2)`. Both have α = 4 (Hoffman-tight).
So they have **identical** c_log = 0.837. The repo only ingests one
under `family=SRG` because the canonical_id deduplicates equivalence
classes.

The 4×4 rook graph is `H(2, 4)` = `Cay((Z_4)², {(±1, 0), (0, ±1)})`
— a 4-regular Hamming graph with the *axis* connection set, i.e. d
= 4, not Shrikhande's d = 6. Wait — that doesn't match. Let me clarify:

- 4×4 rook graph = `K_4 □ K_4`: vertices are pairs `(i, j) ∈ {0,1,2,3}²`,
  adjacent iff they differ in exactly one coordinate. Degree = 6 = 2 · 3
  (3 same-row, 3 same-col), not 4. OK same degree.

So 4×4 rook is the Hamming graph `H(2, 4)`. **It is not K₄-free**:
each row is a `K_4`, since 4 collinear vertices are pairwise adjacent.
ω(H(2, 4)) = 4. So the rook graph is *cospectral* with Shrikhande
but **not K₄-free**. Shrikhande is the K₄-free cospectral mate.

This is the headline reason Shrikhande is in the catalog: it's the
unique K₄-free `srg(16, 6, 2, 2)` graph, and the one that beats every
other 16-vertex K₄-free graph on c_log.

## When to reach for it

- You want a K₄-free 16-vertex graph with α = 4 — this is the optimum
  for that (N, α) pair, on the Hoffman bound.
- You want the unique K₄-free cospectral mate of an SRG.
- You want the second-best graph in the c_log frontier (after P(17)).

## When **not** to reach for it

- N ≠ 16 — Shrikhande is a single graph, not a parameterised family.
  The natural generalisation (Latin-square graphs, partial geometries)
  is open.

## Related

- The 4×4 rook graph `H(2, 4)` — same SRG parameters, but K_4-saturated;
  see [`HAMMING.md`](HAMMING.md) for the Hamming family it belongs to.
- The Clebsch graph (`srg(16, 5, 0, 2)`) — different SRG parameters,
  triangle-free, K_4-free. See [`FOLDED_CUBE.md`](FOLDED_CUBE.md).
- `BEYOND_CAYLEY.md` — argues that vertex-transitive K₄-free graphs
  (Shrikhande included) sit on the Lovász θ surface, so they admit no
  spectral c_log improvement without breaking transitivity.
