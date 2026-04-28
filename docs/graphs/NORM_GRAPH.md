# Norm-kernel Cayley `Cay(Z_{q²−1}, K)`

For a prime `q`, the multiplicative group `F_{q²}^*` is cyclic of order
`q² − 1`. The **norm map** `N : F_{q²}^* → F_q^*`, `N(x) = x^{q+1}`,
has kernel of size `q + 1` (since the image has size `q − 1`). Pick
a generator `ω` of `F_{q²}^*`, identify `F_{q²}^* ≅ Z_{q²−1}` via
`ω^i ↔ i`, and the kernel `K` corresponds to the cyclic subgroup
`{(q − 1) · k mod (q² − 1) : k = 0, 1, …, q}`.

The norm-kernel Cayley graph is

> `Cay(Z_{q²−1}, K)`,

an `(q + 1)`-regular circulant on `q² − 1` vertices with a normal
spectrum inherited from Gauss sums.

> Implemented at
> [`search/algebraic_explicit/norm_graph.py`](../../search/algebraic_explicit/norm_graph.py).
> Ingested under `source="norm_graph"`; results in
> [`graphs/norm_graph.json`](../../graphs/norm_graph.json).

---

## **Headline negative result: K₄-free only at q = 2**

The norm-kernel construction was added as "Probe 5b — algebraic ceiling"
under the assumption that the structured norm-1 subgroup connection set
would force a K₄-free graph for all q. **It does not.** The full
sweep:

| q | N = q² − 1 | α | d_max | c_log (apparent) | K₄-free |
|---:|---:|---:|---:|---:|:---:|
| 2 | 3 | 1 | 2 | 0.961797 | ✓ |
| 3 | 8 | 2 | 3 | 0.682679 | · |
| 5 | 24 | 4 | 5 | 0.517779 | · |
| 7 | 48 | 6 | 7 | 0.449661 | · |
| 11 | 120 | 10 | 11 | 0.382280 | · |
| 13 | 168 | 12 | 13 | 0.362023 | · |

Only `q = 2` (the trivial triangle on 3 vertices) is K₄-free.
Everything else from `q = 3` onwards contains K₄.

The apparent c_log values for q ≥ 3 are *not* valid frontier candidates.
They look frontier-breaking — 0.36 at n = 168 is far below P(17)'s
0.679 — but they are not realised by K₄-free graphs. They are simply
an artefact of the dense norm-kernel connection set giving a high-α-
to-degree ratio in a K₄-saturated regime.

## Why the construction fails for q ≥ 3

The norm-kernel `K ⊂ F_{q²}^*` has size `q + 1`. For `q = 2` that's
3 elements (the triangle is forced). For `q ≥ 3`:

- |K| ≥ 4, so the connection set has ≥ 4 elements.
- K is the kernel of a multiplicative-group homomorphism, so K is
  closed under products (i.e. if `x, y ∈ K` then `x · y ∈ K`).
- Translated to Cayley adjacency: if `g_1, g_2 ∈ K` are connection
  elements, then `g_1 · g_2 ∈ K`, i.e. `g_1 · g_2` is also a connection
  element. So a vertex `v` adjacent to `v · g_1` and `v · g_2` is
  also adjacent to `v · g_1 · g_2`. By symmetry, `v · g_1, v · g_2,
  v · g_1 · g_2` are pairwise adjacent (their pairwise differences
  in K). Combined with `v`, that's a K_4 — *if* one of the pairwise
  ratios is also in K.

Concretely for q = 3: `q² − 1 = 8`, K = {0, 2, 4, 6} (the even
residues mod 8). Take `g_1 = 2, g_2 = 4`: `g_1 · g_2 = 6 ∈ K`. So
`{0, 2, 4, 6}` is a clique of size 4 ⇒ K_4.

## The cyclotomic obstruction

More generally, the Cayley graph `Cay(Z_n, S)` where S is a
multiplicatively closed subgroup of `Z_n^*` (or its image) has K_n-cliques
in proportion to the subgroup size. The norm-kernel is a multiplicative
subgroup of `F_{q²}^*` of order q+1, and that subgroup (under the additive
identification used in the Cayley graph) has K₄ for `q + 1 ≥ 3`.

This is *the* failure mode of "structured Cayley with multiplicatively
closed connection set" — exactly opposite to the power-residue Cayley
construction, where the connection set is a subgroup of *index* k (i.e.
of order `(p−1)/k`), and the construction is K₄-free as long as `k ≥ 2`.

## Eligible N (still listed, but only q = 2 produces a K₄-free graph)

| q | N = q² − 1 |
|---:|---:|
| 2 | 3 |
| 3 | 8 |
| 5 | 24 |
| 7 | 48 |
| 11 | 120 |
| 13 | 168 |
| 17 | 288 |
| 19 | 360 |

The driver runs all of these but the post-build filter drops the q ≥ 3
ones; only q = 2 ends up in `graphs/norm_graph.json`.

## When to reach for it

- You want an explicit example of an algebraic Cayley construction that
  *fails* K₄-freeness due to a multiplicatively-closed connection set.
- You want the q = 2 triangle as a sanity-check ground truth.

## When **not** to reach for it

- You want a K₄-free graph past N = 3 — this family contributes nothing.
- You're chasing the frontier — the apparent c_log values for q ≥ 3
  are spurious (not K₄-free).

## Related

- [`POLARITY.md`](POLARITY.md) — the polarity graph `ER(q)` is the
  *intended* algebraic-ceiling at N = q² + q + 1 (similar N range, but
  *is* K₄-free).
- [`MATTHEUS_VERSTRAETE.md`](MATTHEUS_VERSTRAETE.md) — the
  Mattheus–Verstraete construction uses the *projective-norm graph*
  family but adds a per-pencil bipartization step that explicitly forces
  K₄-freeness; the norm-kernel Cayley alone does not have that step.
- [`CAYLEY.md`](CAYLEY.md) — the "opposite" Cayley construction:
  power-residue subgroups give K₄-free graphs when index ≥ 2 (Paley
  is index 2).
