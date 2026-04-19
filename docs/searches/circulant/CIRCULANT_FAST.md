# `CirculantSearchFast` — scalable circulant search for large `n`

## What it is

A pragmatic replacement for `CirculantSearch` when `n > 35` and exhaustive
enumeration over `S ⊆ {1, ..., n//2}` is infeasible. Not exhaustive —
**best K4-free circulant up to multiplier isomorphism with `|S| ≤
max_conn_size`**. In practice that slice of the circulant lattice
contains every known optimum (Paley `P(17)` has `|S|=4`, circulant best at
`n=34` is `(2, 4, 8, 16)` with `|S|=4`, all others found have `|S| ≤ 4`).

## What it does

Four compounding steps:

1. **DFS over K4-free connection sets.** K4-freeness is monotone in `S`,
   so adding a jump that creates a K4 means no superset can be K4-free.
   Backtrack on hit. The K4 check uses the circulant-aware
   O(|S_full|^3) test (triangle in the "difference graph" on `S_full`)
   rather than a generic graph K4 search.
2. **Multiplier canonicalization.** `C(n, S) ≅ C(n, u·S mod n)` for every
   `u ∈ Z_n*`. Only keep `S` that is lex-smallest in its orbit under this
   action. Cuts the search space by roughly `ϕ(n)/2`.
3. **Greedy-α lower-bound filter.** Random-greedy α is a lower bound on
   the true α, and c is monotone in α. If the greedy α already makes
   `c` worse than the current top-k cutoff, drop the candidate before
   the exact solve.
4. **Exact α via CP-SAT with vertex-transitivity break.** Circulants are
   vertex-transitive, so pinning `x[0]=1` is sound and collapses the MIS
   search by roughly `N`. Pure-Python bitmask B&B gets stuck past
   `n ≈ 60` on sparse K4-free circulants (observed > 45 s per graph at
   `n=80`, `|S|=4`); CP-SAT solves the same instances in 10–100 ms.
   The solver lives in `utils.graph_props.alpha_cpsat`; dispatch is via
   `alpha_auto(..., vertex_transitive=True)`.

## Observed performance (`top_k=1`, `max_conn_size=4`)

| `n`  | best c | `|S|` | `S`                   | wall |
|------|--------|-------|-----------------------|------|
| 17   | 0.679  | 4     | (1, 2, 4, 8)          | <0.1 s |
| 34   | 0.679  | 4     | (2, 4, 8, 16)         | 0.4 s |
| 47   | 0.822  | ≤6    | (1, 2, 9, 10, 14, 15) | 4.6 s |
| 49   | 0.788  | ≤6    | (1, 3, 4, 17, 19, 20) | 5.9 s |
| 60   | 0.769  | 4     | (2, 16, 18, 28)       | 2.1 s |
| 80   | 0.721  | 2     | (10, 20)              | 5.6 s |
| 100  | 0.769  | 4     | (5, 10, 20, 45)       | 15.1 s |

For `n ≤ 20`, results match `CirculantSearch` exactly when `max_conn_size
= n // 2` (sanity checked in `scripts/run_circulant_fast.py`).

## When to reach for it

- You need a strong circulant at `n ≥ 40` as a SAT warm-start.
- You want to populate `graphs/circulant.json` beyond the exhaustive
  cutoff without falling back to random sampling.
- You want to verify whether a new algorithm beats the best circulant
  at a given `n` without running every `S`.

## When **not** to reach for it

- `n ≤ 35` and you want the **true** best: use `CirculantSearch`
  (fully exhaustive, so provably optimal).
- You want to explore `|S| > max_conn_size`. The cap is an intentional
  feasibility constraint; raising it grows the DFS roughly
  `C(n/2, max_conn_size)`.
- You want non-symmetric or non-regular graphs — circulants are regular
  and vertex-transitive by definition.

## Non-obvious failure modes

- **Best is "just outside the cap."** No known circulant optimum has
  `|S| > 4`, but if one exists and sits just beyond `max_conn_size`, the
  search misses it silently. Widen and re-run as a check.
- **Base class α recomputation.** `Search._wrap()` recomputes α on every
  returned graph. It uses `utils.graph_props.alpha` (clique-cover B&B),
  which scales to n ≈ 1000 on sparse K4-free graphs; no override is
  needed here. Earlier versions of this code dispatched to
  `alpha_cpsat(..., vertex_transitive=True)` at large n — the
  clique-cover bound makes that obsolete.

## Open questions

1. Does widening `max_conn_size` to 8 at `n ∈ [50, 100]` find anything
   below `c = 0.679`? The `|S| ≤ 4` slice already matches or hits the
   `1/ln 4 ≈ 0.721` floor at `n=80`, which is suggestive.
2. For prime `n ≡ 1 mod 4`, seeding the DFS at the Paley QR set might
   find local basins faster than the current lex-order DFS. Untested.
3. The multiplier-canonicalization is sufficient but not tight: at
   composite `n`, there can be isomorphic pairs outside the `Z_n*`
   orbit. pynauty canonicalization would close the gap but costs more.
   Worth measuring the duplicate rate.
