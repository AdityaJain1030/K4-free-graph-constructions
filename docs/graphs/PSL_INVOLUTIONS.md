# `Cay(PSL(2, q), trace-0 involutions)`

For prime power q, `PSL(2, q)` = `SL(2, q) / {±I}` is the projective
special linear group of degree 2 over F_q. Its Cayley graph with
the conjugacy class of involutions as connection set is one of the
classical "small simple-group" Cayley constructions.

- |PSL(2, q)| = `q (q² − 1) / gcd(2, q − 1)`. Specifically `q (q²−1)/2`
  for q odd, `q (q² − 1)` for q even (where −I = I forces SL = PSL).
- Connection set: the unique conjugacy class of involutions
  in PSL(2, q). For q odd this is the trace-0 elements of SL(2, q)
  (squared-to-`-I`, i.e. order-2 in PSL); for q even it is the
  SL(2, q) elements with trace 0 excluding the identity.

> Implemented at
> [`search/algebraic_explicit/psl_involutions.py`](../../search/algebraic_explicit/psl_involutions.py).
> Group machinery from
> [`utils/algebra.py`](../../utils/algebra.py) (the `psl2` factory); F_q arithmetic
> from [`utils/algebra.py`](../../utils/algebra.py). Ingested under
> `source="special_cayley"` with `family="PSL"`.

---

## Why this connection set is natural

Among all conjugacy classes of PSL(2, q), the involution class is the
**smallest non-trivial** one for q odd: it has size `q(q+1)/2` (so the
Cayley graph is `q(q+1)/2`-regular). It's also the only conjugacy
class of order-2 elements, so the graph is intrinsic to the group
(no choice of generators).

For q = 2: PSL(2, 2) ≅ S_3, involutions = transpositions, which gives
the complete bipartite graph `K_{3,3}` minus a perfect matching =
the 3-prism. 6 vertices, 3-regular, K₄-free (it has only triangles
in a single direction).

For q = 4: PSL(2, 4) ≅ A_5, involutions = double-transpositions.
**Same Cayley graph** as `Cay(A_5, double-transpositions)` since they
are isomorphic as groups with conjugate connection sets. We dedupe
by N in the driver, so the q=4 case is run only once.

## K₄-freeness — the negative result

Beyond q = 2, the involution-Cayley is **not K₄-free** for any q
tested. Empirically:

| q | n = \|PSL(2,q)\| | K₄-free? | structural reason |
|---:|---:|:---:|---|
| 2 | 6 | ✓ | only the trivial 3-prism |
| 3 | 12 | ✗ | A_4 has a Klein-four subgroup → K_4 inside the involutions |
| 4 ≅ 5 | 60 | ✗ | A_5 contains many Klein-four subgroups |
| 7 | 168 | ✗ | involution conjugacy class is size 21 — too dense |
| 8 | 504 | ✗ | char-2 makes involutions even more abundant |
| 9 | 360 | ✗ | similar to q = 7 |
| 11 | 660 | ✗ | |
| 13 | 1092 | ✗ | |

The structural witness for K₄ in PSL(2, q) for q ≥ 3: every Klein-four
subgroup `V_4 ≤ PSL(2, q)` consists of three involutions plus the
identity. Those three involutions are pairwise products of each other
(`a · b = c`, etc.), so in the Cayley graph any vertex `g` is adjacent
to `g·a, g·b, g·c`, and these three are pairwise adjacent
(`(g·a) · (g·b)^{-1} = a · b^{-1} = c`, an involution). So `{g, ga,
gb, gc}` forms a K_4.

PSL(2, q) for q ∈ {3, 4, 5, 7, 8, 9, 11, 13} all contain Klein-four
subgroups. Only PSL(2, 2) = S_3 does not (S_3 has no V_4 — its only
non-trivial subgroup is the cyclic `<(123)>` of order 3 plus the
three order-2 subgroups; no two order-2 elements commute).

## Why this is the only useful instance

The single K₄-free hit is `PSL(2, 2) = S_3`, the 6-vertex 3-prism.
Its parameters:

| n | q | c_log | α | d_max |
|---:|---:|---:|---:|---:|
| 6 | 2 | 1.365359 | 3 | 3 |

So this family contributes exactly one graph to the K₄-free DB, and
it's a small-N data point with c_log well above the frontier. The
family is closed *for this connection set*.

## Open extension — alternative connection sets

The involution class is the most natural pick but not the only one.
PSL(2, q) has other conjugacy classes:

- **3-cycles** (q ≡ ±1 mod 3): conjugacy class of order ≤ N/3.
- **Order-q elements**: parabolic class, size N(q-1)/q.
- **Elements of split-torus order (q-1)/2**: size N · 2.
- **Elements of non-split-torus order (q+1)/2**: size N · 2.

A k-cycle conjugacy class generates a smaller Cayley graph (since
inverses of 3-cycles are 3-cycles, the connection set is symmetric)
and might dodge the Klein-four-K₄ obstruction. None of these have been
swept; doing so is an open question — see
[`experiments/algebraic_explicit/README.md`](../../experiments/algebraic_explicit/README.md)
"alternate connection sets" item.

## When to reach for it

- You want the unique K₄-free small-group Cayley with non-abelian
  symmetry (PSL(2, 2) = S_3).
- You want a sanity-check that the algebraic-construction infrastructure
  works for a non-trivial group (the n=6 graph is the simplest test).

## When **not** to reach for it

- You want a competitive `c_log` — only the n=6 case is K₄-free, and
  even at that small N c_log = 1.365.
- You're hoping any PSL(2, q ≥ 3) involution-Cayley is K₄-free —
  it's not, structurally, due to Klein-four subgroups.

## Related

- [`A5_DOUBLE_TRANSPOSITIONS.md`](A5_DOUBLE_TRANSPOSITIONS.md) — same
  graph as PSL(2, 4) ≅ PSL(2, 5) involution-Cayley, redundant in the
  current driver. The `A5DoubleTranspositionsSearch` class still
  exists to make the A_5 → S_n group structure explicit.
- `CAYLEY.md` — abelian Cayleys (Cay(Z_p, R_k)) — completely different
  K₄-freeness regime.
- The PSL(2, q) story sits inside the broader "Cayley over a non-abelian
  group" story — `CAYLEY_TABU_GAP.md` (search-shaped) is the
  search-based counterpart that *can* find K₄-free Cayleys on PSL(2, q)
  groups by choosing connection sets carefully.
