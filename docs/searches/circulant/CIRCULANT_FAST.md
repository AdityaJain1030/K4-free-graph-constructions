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
   search by roughly `n`. CP-SAT solves most instances in 10–100 ms even
   past `n = 200`. The generic clique-cover B&B (`alpha_bb_clique_cover`)
   was tried and rejected: on sparse connection sets (`|S| ≤ 2`) at
   `n = 80` it takes 0.8 s per call on average, up to 12 s in the tail,
   because the clique-cover upper bound is loose on low-density graphs.
   The solver lives in `utils.graph_props.alpha_cpsat`; `_alpha_of` in
   this class calls it with `vertex_transitive=True` so the base class
   doesn't fall back to clique-cover when re-scoring the returned graph.

## Observed performance (`top_k=1`, `max_conn_size=4`)

Measured on `2026-04-19` after switching back to CP-SAT for exact α (see
section 4 above). All runs on the local WSL box (single core, no
parallelism).

| `n` | best c | `|S_half|` | `d` | wall |
|-----|--------|------------|-----|------|
| 17  | 0.679  | 4          | 8   | 0.02 s |
| 23  | 0.836  | 4          | 8   | 0.03 s |
| 34  | 0.679  | 4          | 8   | 0.19 s |
| 47  | 0.855  | 3          | 6   | 0.60 s |
| 50  | 0.804  | 3          | 6   | 0.53 s |
| 80  | 0.721  | 2          | 4   | 8.6 s  |
| 100 | 0.769  | 4          | 8   | 18.0 s |
| 118 | 0.908  | 3          | 6   | 263 s  |
| 130 | 0.773  | 3          | 6   | 58 s   |
| 150 | 0.769  | 4          | 8   | 104 s  |
| 160 | 0.721  | 2          | 4   | 185 s  |
| 200 | 0.721  | 2          | 4   | 339 s  |

Note: `n = 47` reports `c = 0.855 (|S|=3, d=6)` because `max_conn_size=4`
caps |S_half|. The known `c = 0.822` at `n = 47` needs `|S_half| = 6`
(`(1, 2, 9, 10, 14, 15)`) and will not be found here. Widen the cap if
that regime matters.

Wall time is dominated by pass 2 CP-SAT calls, not the DFS or the
greedy pre-filter. Per-call CP-SAT cost is dominated by ~100 ms of
OR-Tools solver init — so wall time scales with the number of
candidates that survive the greedy filter, which in turn depends on
how tight the greedy lower bound is. When the best `|S|` is small
(`d = 4` at `n = 80, 160, 200`) the greedy bound is loose and many
candidates survive; when the best `|S|` hits `d = 8` (e.g. `n = 100,
150`) pruning is much more effective. That's why `n = 118` is slower
than `n = 130` despite being smaller — the best circulant at 118 has
`c = 0.908`, a loose cutoff that keeps many d=4 candidates alive.

For `n ≤ 20`, results match `CirculantSearch` exactly when `max_conn_size
= n // 2` (sanity checked in `scripts/run_circulant_fast.py`).

### Implications for SAT warm-starts

- `n ≤ 100` returns in **under 30 s** — cheap enough to run per-SAT
  invocation as a baseline to beat.
- `n ∈ [100, 200]` is **1–6 min** per n, dominated by CP-SAT overhead.
  Generate once, cache to `graphs/circulant_fast.json`, and reuse.
- `n ∈ [200, 300]` extrapolates to **5–15 min** per n. Do these on the
  server, not the laptop, and in a one-shot batch — the per-n cost is
  dominated by a few hundred CP-SAT startup overheads, not solve time,
  so spreading across cores (one n per core) is the right partition.

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
  returned graph. The default `_alpha_of` uses clique-cover B&B, which
  hangs for seconds on low-density circulants (|S|≤2). We override
  `_alpha_of` here to call `alpha_cpsat(..., vertex_transitive=True)`
  directly; don't remove that override without reconfirming the wall
  times in the table above.

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
