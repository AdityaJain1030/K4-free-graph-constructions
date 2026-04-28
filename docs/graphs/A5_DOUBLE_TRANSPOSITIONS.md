# `Cay(A_5, all 15 double-transpositions)`

The alternating group A_5 has 60 elements. Its conjugacy classes are:

| class | order | size |
|---|---|---|
| identity | 1 | 1 |
| 3-cycles | 3 | 20 |
| double-transpositions (e.g. (12)(34)) | 2 | 15 |
| 5-cycles, type α | 5 | 12 |
| 5-cycles, type β | 5 | 12 |

The double-transpositions form a 15-element conjugacy class closed
under inversion (each element is self-inverse since order 2). Taking
this as the connection set gives the Cayley graph
`Cay(A_5, double-transpositions)`: 60 vertices, 15-regular.

> Implemented at
> [`search/algebraic_explicit/a5_double_transpositions.py`](../../search/algebraic_explicit/a5_double_transpositions.py).
> Returns the 60-vertex 15-regular graph; the driver filter rejects it
> as not K₄-free.

---

## Why this graph is **not** K₄-free

A_5 has Klein-four subgroups `V_4 ⊆ A_5` (e.g.
`{e, (12)(34), (13)(24), (14)(23)}`). Any such V_4 has three
non-identity elements, all involutions, all double-transpositions.
For any `g ∈ A_5`, the four elements `{g, g·(12)(34), g·(13)(24),
g·(14)(23)}` are pairwise adjacent in the Cayley graph because the
ratios are all double-transpositions:

- `g · (12)(34) · ((13)(24))^{-1} = (12)(34) · (13)(24) = (14)(23)` —
  also a double-transposition ✓.
- Similarly for the other pairs.

So every coset of every V_4 ≤ A_5 produces a K_4 in the Cayley graph.
A_5 has 5 conjugate Klein-four subgroups, each giving 60/4 = 15 coset
K_4's, for a total of 5 × 15 = 75 K_4's in the graph (not all
distinct — there's some overlap).

The K₄-freeness failure is **structural** and shared with
`Cay(PSL(2, q), involutions)` for any q where PSL(2, q) contains a
Klein-four subgroup (i.e. all q except q = 2). Since
PSL(2, 5) ≅ A_5, this is the same Cayley graph as
`Cay(PSL(2, 5), involutions)` and (since PSL(2, 4) ≅ PSL(2, 5)) as
`Cay(PSL(2, 4), involutions)`.

## Why this class still exists

Three reasons the search class is kept rather than deleted:

1. **Documentation.** It's the simplest A_5 Cayley to describe and
   write down explicitly, and pedagogically a good "smallest non-trivial
   non-abelian Cayley" example.
2. **Negative-result anchor.** The K₄-failure has a clean structural
   reason (Klein-four subgroups → K₄). Having a class produce the graph
   makes it concrete; you can pull it from `graph_db` and inspect the
   K₄ structure.
3. **Future alternative-connection-set work.** A_5 has other connection
   sets (3-cycles → 20-element class; 5-cycles → 12-element classes
   per type), some of which might be K₄-free. The current class is the
   "obvious" one; future classes (`A5ThreeCyclesSearch` etc.) would
   slot in alongside.

## Driver behaviour

`A5DoubleTranspositionsSearch(n=60).run()` builds the graph
unconditionally; the driver
([`experiments/algebraic_explicit/run.py`](../../experiments/algebraic_explicit/run.py))
filters non-K₄-free results before saving. So calling the driver with
`--construction a5_double_transpositions` runs the construction,
prints `[a5_double_transpositions n=60] skipped (dropped 1 non-K4-free)`,
and saves nothing.

## When to reach for it

- You want a concrete 60-vertex 15-regular Cayley to inspect.
- You're comparing K₄-free vs K₄-containing Cayley graphs structurally.
- You're working out the connection-set theory and want a known-bad
  example.

## When **not** to reach for it

- You want anything K₄-free — this isn't.
- You want a graph that ingests cleanly into the K₄-free DB — the
  driver filter drops it.

## Related

- [`PSL_INVOLUTIONS.md`](PSL_INVOLUTIONS.md) — same Cayley graph (since
  A_5 ≅ PSL(2, 4) ≅ PSL(2, 5)).
- The A_5 + 3-cycle Cayley (not yet implemented) would have connection
  set of size 20 instead of 15. Expected to also have K₄ via different
  subgroup structure (every 3-cycle generates Z_3, and `<a, b>` for two
  3-cycles can hit A_4 or A_5 itself), but worth verifying.
- `CAYLEY_TABU.md` — generic search over Cayley connection sets; finds
  K₄-free A_5 Cayleys for *some* connection sets, just not the
  double-transpositions one.
