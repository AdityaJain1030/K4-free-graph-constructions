# The folded (d+1)-cube `Cay(Z_2^d, {e_1, …, e_d, (1,…,1)})`

The folded (d+1)-cube `□^d_*` is the graph on `2^d` vertices where two
vertices `u, v ∈ Z_2^d` are adjacent iff their symmetric difference
`u ⊕ v` is either a unit vector `e_i` (single-coordinate flip) or the
all-ones vector `(1, 1, …, 1)`. Equivalently:

- It is the Cayley graph `Cay(Z_2^d, S_d)` with connection set
  `S_d = {e_1, …, e_d, 𝟙}`.
- It is the quotient of the (d+1)-cube `Q_{d+1}` by its antipodal map
  `x ↦ x ⊕ 𝟙_{d+1}`. (Hence "folded (d+1)-cube".)

Numbered instances:

- `d = 3` → `K_{4,4}` (8 vertices, 4-regular, bipartite).
- `d = 4` → **Clebsch graph** (16 vertices, 5-regular, srg(16, 5, 0, 2),
  triangle-free).
- `d = 5` → folded 6-cube (32 vertices, 6-regular, bipartite).
- `d = 6` → folded 7-cube (64 vertices, 7-regular, distance-regular,
  not bipartite).
- `d = k` → folded (k+1)-cube on 2^k vertices.

> Implemented at
> [`search/algebraic_explicit/folded_cube.py`](../../search/algebraic_explicit/folded_cube.py).
> Graphs are ingested under `source="special_cayley"` with metadata
> `family="FoldedCube"`; results sit in
> [`graphs/special_cayley.json`](../../graphs/special_cayley.json).

---

## Why this family is K₄-free

A triangle in `Cay(Z_2^d, S)` corresponds to three (not necessarily
distinct) elements `s_1, s_2, s_3 ∈ S` with `s_1 + s_2 + s_3 = 0` in
Z_2^d. Equivalently `s_3 = s_1 ⊕ s_2`, so the question reduces to: is
`S_d` closed under pairwise XOR?

For `S_d = {e_1, …, e_d, 𝟙}`:
- `e_i ⊕ e_j` (i ≠ j): weight 2 in Z_2^d, not in `S_d` (since `S_d` only
  has weight-1 and weight-d elements; weight 2 ≠ 1 unless d = 2, and
  ≠ d unless d = 2).
- `e_i ⊕ 𝟙`: weight d−1, not in `S_d` for d ≥ 3.
- `𝟙 ⊕ 𝟙 = 0`, not in `S_d`.

So for `d ≥ 3` the connection set is XOR-pairwise-disjoint from itself.
The folded (d+1)-cube is **triangle-free** for `d ≥ 3`, hence K₄-free
trivially. (At `d = 2` the connection set is {e_1, e_2, (1,1)} =
{(1,0), (0,1), (1,1)}; these XOR-sum to 0, giving a triangle. This
happens because at d = 2, weight d−1 = weight 1 collides.)

The triangle-free conclusion alone is the headline. K₄-freeness is a
direct corollary: any K₄ would contain a triangle.

## Bipartiteness

The folded (d+1)-cube is bipartite iff `d` is **odd**.

- The standard d-cube `Q_d = Cay(Z_2^d, {e_i})` is always bipartite by
  Hamming-weight parity.
- Adding the edge `𝟙` (an all-ones move) flips parity by `d mod 2`, so:
  - `d` odd → `𝟙`-flips also reverse parity → bipartite preserved.
  - `d` even → `𝟙`-flips preserve parity → adds an odd-cycle equivalent,
    breaks bipartiteness.

Bipartite folded cubes (`d ∈ {3, 5, 7, 9, …}`) have α = 2^(d−1) by
construction (the bipartition is the largest independent set), giving
a useless `c_log = α · d_max / (N · ln d_max) = (d+1) / ln(d+1)` —
this *grows* with d. Non-bipartite cases (`d ∈ {4, 6, 8, …}`) are the
only ones worth examining.

## Why d = 4 (Clebsch) is the strongest

For non-bipartite cases the parameter relations are:
- N = 2^d
- d_max = d + 1
- α(Clebsch, d=4) = 5; α(folded 7-cube, d=6) = 22 (so α/N = 5/16 = 0.31
  vs 22/64 = 0.34 — both at the bipartite-fraction-α scaling)

For Clebsch, the SRG structure forces α = 5: it is `srg(16, 5, 0, 2)`,
so `λ_2 = 1` and the Hoffman bound gives `α ≤ 16·1/(5+1) = 16/3 ≈ 5.33`,
saturated at α = 5.

For larger d, the Hoffman saturation degrades — the second eigenvalue
of the folded (d+1)-cube grows like `O(d)` and α grows roughly as `2^d /
(d+1)`. So `c_log = α·d_max / (N·ln d_max) ≈ 1 / ln(d+1)`, which
**decreases** asymptotically — but only slowly. Empirically:

| d | n=2^d | α | d_max | c_log |
|---:|---:|---:|---:|---:|
| 3 | 8 | 4 | 4 | 1.4427 |
| 4 | 16 | 5 | 5 | **0.9708** |
| 5 | 32 | 16 | 6 | 1.6743 |
| 6 | 64 | 22 | 7 | 1.2366 |
| 7 | 128 | 64 | 8 | 1.9236 |

Bipartite (odd d) rows are degenerate; among non-bipartite (even d)
rows, Clebsch (d=4) is best. d = 6 already loses ground.

## When to reach for it

- You want a vertex-transitive K₄-free benchmark at exactly N = 16 or
  N = 64 with closed-form spectral structure.
- You want a structured starting graph for an edge-switch polish —
  the spectrum is fully determined, so you can compare polish runs
  against a known starting Hoffman bound.

## When **not** to reach for it

- N is not a power of 2 — the family doesn't cover those.
- You want competitive `c_log` past N = 16 — only Clebsch is close to
  the polarity / Cayley frontier; larger d falls off.
- You want bipartite K₄-free graphs as a useful objective — they're
  trivially K₄-free with α = N/2, and the bipartite folded cubes have
  no advantage over `K_{N/2,N/2}` directly.

## Related

- `CAYLEY.md` — power-residue Cayley graphs (`PrimeCirculantSearch`),
  the other "structured Cayley over Z_p^?" family.
- `BLOWUP.md` — lex/tensor-blow-up of Clebsch (or any folded cube) is
  not currently in scope but would be a natural extension at higher N.
- The Clebsch graph is also the line graph of the Kneser graph K(5, 2)
  / Petersen-line graph; see [Wikipedia](https://en.wikipedia.org/wiki/Clebsch_graph)
  for the dozen alternative descriptions.
