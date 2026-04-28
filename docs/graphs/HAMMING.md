# Hamming graphs `H(d, q) = Cay(Z_q^d, {±e_i})`

The Hamming graph `H(d, q)` is the graph on `Z_q^d` where two vertices
are adjacent iff they differ in exactly one coordinate. Equivalently:

- Vertex set: `Z_q^d` (cardinality `q^d`).
- Edge set: pairs `u, v ∈ Z_q^d` with Hamming distance 1.
- Cayley realisation: `Cay(Z_q^d, {±e_i : 1 ≤ i ≤ d})`, connection set
  size `2d` for q ≥ 3, size `d` for q = 2 (because `+e_i = -e_i` over
  F_2).

Numbered instances:

- `H(d, 2)` = the d-dimensional **hypercube** `Q_d` (bipartite,
  d-regular, 2^d vertices).
- `H(2, 3)` = the 3×3 **rook graph** `K_3 □ K_3` (9 vertices, 4-regular).
- `H(d, 3)` = the d-dimensional ternary Hamming graph (q^d vertices,
  2d-regular).
- `H(2, q)` for q ≥ 4 = the q×q rook graph (q² vertices, 2(q−1)-regular).

> Implemented at
> [`search/algebraic_explicit/hamming.py`](../../search/algebraic_explicit/hamming.py).
> Graphs ingested under `source="special_cayley"` with
> `family="Hamming"`. Default sweep covers `q ∈ {2, 3}, d ∈ [2, 6]`
> in [`graphs/special_cayley.json`](../../graphs/special_cayley.json).

---

## Clique structure determines K₄-freeness

`H(d, q)`'s maximal cliques are exactly the **lines** of the Hamming
scheme: for each axis `i` and each fixed assignment of the other `d−1`
coordinates, the q-clique `{(c_1, …, c_{i-1}, x, c_{i+1}, …, c_d) : x ∈ Z_q}`.

So clique number ω(H(d, q)) = q. Therefore:

- `q = 2` ⇒ ω = 2, the graph is triangle-free (in fact bipartite). K₄-free
  trivially.
- `q = 3` ⇒ ω = 3, triangles abound but K₄ is forbidden — every K₄
  would need 4 mutually adjacent points lying on a common axis, but
  axes have only q = 3 points.
- `q ≥ 4` ⇒ ω ≥ 4, K₄ is **present** along every axis, so the
  construction is **not K₄-free**.

The `HammingSearch` class accepts any `(d, q)`; the driver filter drops
the resulting graph for `q ≥ 4`. Eligible-N for `q ∈ {2, 3}`:

- `q = 2`: N ∈ {4, 8, 16, 32, 64, 128, 256, …} = {2^d : d ≥ 2}
- `q = 3`: N ∈ {9, 27, 81, 243, 729, …} = {3^d : d ≥ 2}

## Spectrum and α

`H(d, q)` is the d-fold tensor power of the complete graph `K_q`, in
the sense that `A(H(d, q)) = ⊕_{i=1}^d (I_{q^{d-1}} ⊗ A(K_q))`. So
its spectrum is

```
λ(H(d, q)) = {q · (#{i : ε_i = 1}) − d : ε ∈ {0, 1}^d}
           = {-d, q − d, 2q − d, …, dq − d = d(q − 1)}
```

with multiplicities `\binom{d}{i} (q-1)^i`. The largest eigenvalue is
`d(q − 1)` (the regularity), the smallest is `−d`.

Hoffman bound: `α(H(d, q)) ≤ q^d · d / (d(q − 1) + d) = q^d / q = q^(d-1)`.
This is **saturated**: take `S_α = {(c_1, …, c_d) : c_1 = 0}`, an
independent set of size `q^(d-1)`. So:

- α(H(d, q)) = q^(d-1) (exactly).
- d_max = d(q − 1).
- c_log = α · d_max / (N · ln d_max) = q^(d-1) · d(q-1) / (q^d · ln(d(q-1)))
       = d(q-1) / (q · ln(d(q-1))).

For fixed q this is `Θ(d / log d)` — c_log **grows** with d. So among
K₄-free Hamming graphs (q ∈ {2, 3}), the smallest d wins per fixed q.

| n | d | q | c_log | α | d_max | notes |
|---:|---:|---:|---:|---:|---:|---|
| 9 | 2 | 3 | **0.961797** | 3 | 4 | rook K_3 □ K_3 |
| 27 | 3 | 3 | 1.116221 | 9 | 6 | |
| 81 | 4 | 3 | 1.282396 | 27 | 8 | |
| 8 | 3 | 2 | 1.365359 | 4 | 3 | 3-cube |
| 4 | 2 | 2 | 1.442695 | 2 | 2 | C_4 = K_{2,2} |
| 16 | 4 | 2 | 1.442695 | 8 | 4 | 4-cube |
| 32 | 5 | 2 | 1.553337 | 16 | 5 | 5-cube |
| 64 | 6 | 2 | 1.674332 | 32 | 6 | 6-cube |

The `q = 3` branch is the more interesting one (ternary Hamming gives
non-bipartite K₄-free graphs with full SRG-like structure at d = 2),
but even its leader `H(2, 3)` at c_log ≈ 0.96 sits well above the
Paley P(17) frontier.

## Why this family doesn't beat the frontier

The c_log floor is forced by the formula above:

```
c_log(H(d, q)) = d (q−1) / (q · ln(d (q−1)))
```

- Minimising d at fixed q ⇒ smallest c_log.
- At `q = 2, d = 2`: c_log = 2/(2 · ln 2) = 1/ln(2) ≈ 1.443.
- At `q = 3, d = 2`: c_log = 4/(3 · ln 4) = 0.962.
- At `q = 3, d = 3`: c_log = 6/(3 · ln 6) = 1.116.

The `q = 3, d = 2` value (the 3×3 rook graph) is the asymptotic floor
of the K₄-free Hamming family — exact, no slack. P(17)'s 0.679 sits
40% below this. So Hamming graphs are systematically out-classed by
power-residue Cayley constructions.

## When to reach for it

- You want a closed-form regular vertex-transitive K₄-free graph on
  `2^d` (q=2 branch) or `3^d` (q=3 branch) vertices.
- You want a Hoffman-saturated graph for sanity-checking spectral α
  bounds.
- You want a "trivial" comparison for a more clever construction —
  the Hamming family has no slack between α and the Hoffman bound, so
  beating Hamming requires actively-K₄-saturated structure.

## When **not** to reach for it

- You want a competitive `c_log`: even the best Hamming sits 40% above
  P(17).
- N is not of the form `2^d` or `3^d` — the family doesn't cover those.
- q ≥ 4 — the construction is not K₄-free.

## Related

- `FOLDED_CUBE.md` — the folded (d+1)-cube uses `Cay(Z_2^d, ±e_i ∪ {𝟙})`,
  one extra connection element compared to `H(d, 2)`. The extra `𝟙` cuts
  α roughly in half (Hoffman saturation drops because of the extra
  spectral element) and gives competitive `c_log` only at `d = 4`
  (Clebsch).
- `CAYLEY.md` — power-residue Cayley graphs reach lower `c_log` at the
  same N for many (n, q) combinations.
