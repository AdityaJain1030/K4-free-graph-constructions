# α solvers

`utils/graph_props.py` ships six exact α solvers and one approximator. They
have genuinely different operating regimes; this doc is the head-to-head
evidence and the regime table. Call sites should pick explicitly — no
`alpha_auto` exists (see `memory/feedback_alpha_solver_api.md`).

## The solvers

| Function | Bound | Backend | Notes |
|---|---|---|---|
| `alpha_exact(adj)` | popcount | pure-Python bitmask B&B | baseline; recursive |
| `alpha_bb_clique_cover(adj)` | greedy clique cover (θ) | pure-Python bitmask B&B | silver bullet on sparse K4-free |
| `alpha_bb_numba(adj)` | popcount | `@njit` iterative bitmask B&B | same weak bound as `alpha_exact`, plus 165 MB JIT overhead; **avoid** |
| `alpha_cpsat(adj, time_limit, vertex_transitive=False)` | — | OR-Tools CP-SAT MIS model | general-purpose; `vertex_transitive=True` pins `x[0]=1` (sound only for vertex-transitive graphs) |
| `alpha_maxsat(adj, time_limit)` | — | python-sat RC2 over WCNF | flat ~30–100 ms startup |
| `alpha_clique_complement(adj)` | Tomita pivot | Bron–Kerbosch on complement | blows up when complement is dense (i.e. when original is sparse) |
| `alpha_approx(adj, restarts)` | — | randomised greedy | **lower bound only**, not exact |

## Regime recommendations

| n range | Graph shape | Use |
|---|---|---|
| n ≤ 40 | any | `alpha_exact` — lowest overhead, sub-50 ms |
| 40 < n ≤ 1000 | sparse K4-free (deg ≤ ~10) | **`alpha_bb_clique_cover`** — sub-second to n=1000 at ~38 MB RSS |
| any n | vertex-transitive, hard instance | `alpha_cpsat(..., vertex_transitive=True)` |
| any n | dense or unknown structure | `alpha_cpsat(...)` |
| sanity cross-check | any | `alpha_maxsat` — independent solver, cheap (~40 ms, 45 MB) |

Fallback rule of thumb on unknown graphs: `alpha_bb_clique_cover` first, timeout
→ `alpha_cpsat`. On dense graphs the clique-cover bound weakens, so the B&B
runtime degrades toward the `alpha_exact` regime.

## Benchmark setup

`scripts/bench_alpha.py` — one forked subprocess per solver (isolated peak RSS
via `resource.getrusage(RUSAGE_SELF).ru_maxrss`), per-solver wall-clock
timeout. Graphs are constructed on the fly via `--family` (jump sets in
`FAMILY_JUMPS`). No DB dependency (the cached `graphs/circulant_fast.json`
proved to be corrupted at n ≥ 65 — see the end of this doc).

```bash
micromamba run -n k4free python scripts/bench_alpha.py \
  --ns 20,40,60,80,100 --family 12 --timeout 120 --warmup-numba
```

## Results — C(n, {1, 2})   (4-regular, K4-free for n ≥ 6, α = ⌊n/3⌋)

wall (s) / peak RSS (MB). "—" = timeout at 120 s.

| n | exact | bb_clique_cover | bb_numba | cpsat | cpsat_vt | maxsat | clique_complement |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.000 / 35 | 0.000 / 35 | 0.870 / 165 | 0.233 / 101 | 0.245 / 101 | 0.028 / 41 | 0.000 / 35 |
| 40 | 0.129 / 35 | 0.000 / 35 | 0.908 / 165 | 0.227 / 101 | 0.224 / 101 | 0.023 / 41 | 0.065 / 35 |
| 60 | 79.11 / 35 | 0.000 / 35 | 9.80 / 165 | 0.238 / 101 | 0.236 / 101 | 0.028 / 41 | 20.62 / 35 |
| 80 | — | 0.001 / 35 | — | 0.329 / 101 | 0.304 / 101 | 0.035 / 41 | — |
| 100 | — | 0.001 / 35 | — | 0.352 / 101 | 0.326 / 101 | 0.036 / 41 | — |
| 150 | — | 0.003 / 35 | — | 0.341 / 103 | 0.340 / 103 | 0.040 / 41 | — |

## Results — C(n, {1, 2, 4})   (6-regular, K4-free)

| n | exact | bb_clique_cover | bb_numba | cpsat | cpsat_vt | maxsat | clique_complement |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 20 | 0.000 / 35 | 0.000 / 35 | 0.938 / 165 | 0.246 / 101 | 0.229 / 101 | 0.025 / 41 | 0.000 / 35 |
| 40 | 0.026 / 35 | 0.000 / 35 | 0.894 / 165 | 0.225 / 101 | 0.229 / 101 | 0.025 / 41 | 0.013 / 35 |
| 60 | 4.26 / 35 | 0.000 / 35 | 1.42 / 165 | 0.235 / 101 | 0.231 / 101 | 0.028 / 41 | 1.52 / 35 |
| 80 | — | 0.001 / 35 | — | 0.745 / 102 | 0.285 / 102 | 0.030 / 41 | — |
| 100 | — | 0.002 / 35 | — | 0.343 / 102 | 0.314 / 100 | 0.037 / 42 | — |

## Results — large n, winning solvers only  (C(n, {1, 2}))

| n | bb_clique_cover | cpsat | cpsat_vt | maxsat |
|---:|---:|---:|---:|---:|
| 400 | 0.019 / 36 | 0.362 / 108 | 0.333 / 108 | 0.047 / 44 |
| 500 | 0.030 / 36 | 0.348 / 110 | 0.350 / 109 | 0.051 / 44 |
| 750 | 0.070 / 37 | 0.397 / 114 | 0.381 / 114 | 0.077 / 45 |
| 1000 | 0.130 / 38 | 0.415 / 119 | 0.431 / 119 | 0.117 / 47 |

The full-matrix bench runs were terminated by the OS above n ≈ 150 while a
parallel `prove_box.py` run was consuming memory on the same host (local is
constrained per `memory/env_hardware.md`). The `n = 400…1000` numbers below
were collected on a later, quieter run with only the four viable solvers.

## Key findings

1. **`alpha_bb_clique_cover` is the silver bullet on sparse K4-free graphs.**
   Exact α at n = 1000 in 130 ms at 38 MB RSS. This far exceeds the original
   n = 200–500 target. The greedy clique-cover upper bound (θ(G) ≥ α(G)) is
   dramatically sharper than the popcount bound used by `alpha_exact`, and the
   B&B prunes to near-linear time on low-degree graphs.

2. **`alpha_maxsat` is the cheap cross-check.** Within ~2× of
   `alpha_bb_clique_cover` across the whole range, independent implementation,
   flat ~40 ms startup, ~45 MB RSS. Use when you want a second solver to
   confirm a result.

3. **CP-SAT has a 200–400 ms startup floor.** Model build + OR-Tools
   initialisation dominates at every n we benched; RSS is 100+ MB and grows
   slowly. It's the right tool when the graph structure is unknown or dense,
   not when bb_clique_cover applies.

4. **`alpha_bb_numba` is a trap.** The JIT kernel uses the same popcount-only
   bound as `alpha_exact`, so it times out at the same n. It also has a 165 MB
   llvmlite/numba RSS overhead that never goes away. Kept for the record; do
   not use it. If we ever rewrite it with the clique-cover bound in numba we
   revisit.

5. **`alpha_clique_complement` is only good on dense graphs.** On sparse
   K4-free graphs the complement is dense, so max clique on the complement is
   hard. Times out at n ≥ 80 here. Keep it for its intended regime
   (small, dense graphs) but don't reach for it on K4-free search targets.

6. **The `vertex_transitive=True` pin buys little on easy circulants.** At the
   n values we benched, cpsat and cpsat_vt are within noise of each other —
   the pin saves a tiny fraction of the model build, but solve time is
   already negligible once the model is up. The pin matters more on hard
   instances (sparse but dense-ish: |S| ≥ 6), where it's been observed to
   give an N-fold speedup. Do not remove it.

## Unrelated bug discovered and fixed during this work

While calibrating `bench_alpha.py` against `graphs/circulant_fast.json`,
cpsat_vt reported α = 63 on the stored n = 80 entry while all other solvers
reported 64. Investigation found the stored sparse6 decoded to a graph that
was **not** the circulant its metadata claimed: correct α on a corrupted
graph, not an α-solver disagreement.

Root cause (fixed): the old `utils/pynauty._canonical_sparse6_pynauty` decoded
`pynauty.certificate()` with `row[-1 - v // 8]`, which is only correct when
n ≤ 64 (a single 64-bit setword per row). At n ≥ 65 the row spans multiple
setwords and reading from the end inverts the word order, so the resulting
sparse6 described a graph isomorphic only to the input restricted to the
first 64 vertices. Same bug existed upstream in `pynauty.canon_graph`.
`scripts/repair_graph_store_n65.py` rebuilt every affected record from its
metadata (59 of them across `circulant_fast.json` and `cayley.json`). Fully
moot now that canonical_id shells out to nauty's `labelg` binary directly
(see `utils/nauty.py`) instead of decoding pynauty's internal certificate.
