# `MattheusVerstraeteSearch` — intuition, caveats, scope

## What Hq\* is

From Mattheus & Verstraete, *The asymptotics of r(4, t)*
(arXiv:2306.04007, 2024). The paper constructs an explicit K₄-free graph
`Hq*` that realizes `r(4, t) = Ω(t³ / log⁴ t)`, closing the long-open gap
in the off-diagonal Ramsey number up to a `log² t` factor. `Hq*` is the
first explicit (non-probabilistic) construction to achieve this order.

The construction, for prime power `q`:

1. Work in `F_{q²}`. The **Hermitian unital** `H ⊂ PG(2, q²)` is the set
   of projective points `⟨x, y, z⟩` satisfying
   `x^(q+1) + y^(q+1) + z^(q+1) = 0`. It has `q³ + 1` points.
2. A **secant** is a line of `PG(2, q²)` meeting `H` in exactly `q+1`
   points. There are `q²(q²−q+1)` of them — these are the vertices of
   our graph.
3. `Hq`: two secants are adjacent iff they meet at a unital point.
4. `Hq` has `q³+1` maximal cliques (**pencils**), one per unital point;
   each pencil is the set of `q²` secants through that point. Two
   distinct pencils share at most one vertex (Prop 2.ii).
5. `Hq` is **not** K₄-free, but Prop 2.iv says every `K₄` has at least
   three vertices lying in some common pencil.
6. `Hq*`: for each pencil `P`, sample a random bipartition `(A_P, B_P)`
   by flipping an independent fair coin for each vertex; replace the
   clique on `P` by the complete bipartite graph `(A_P, B_P)`.
7. `Hq*` is K₄-free: any would-be `K₄` has three vertices in some
   pencil `P`; after bipartition, `Hq*[V(P)]` is triangle-free, so those
   three vertices don't form a triangle, so no `K₄` survives.

Because two pencils share ≤ 1 vertex, **every edge of `Hq` belongs to
exactly one pencil**, so per-pencil bipartition has no edge-level
conflicts — the construction is a straight loop over pencils.

## Why it's here

Not to win `c_log`. A back-of-envelope (using the paper's bound
`α = O(q^{4/3} log^{4/3} q)`, `d ≈ q³`, `n ≈ q⁴`) gives

    c_log(Hq*) ≈ q^{1/3} · log^{1/3} q / 3

which **grows** with `q`. At `n=63` (q=3) expect `c_log ≈ 1.9`; at
`n=525` (q=5) roughly `c_log ≈ 2.3`. Both well above SAT's best in the
same range (`c ≈ 0.72`).

The point is to have a **principled explicit construction from the
literature** sitting in the same logging and persistence surface as
every other search, so future LLM / metaheuristic / SAT-extension work
has a named, citable baseline to be compared against. Plug into
`graph_db` once and cite the arXiv paper in notebooks forever.

## n coverage

V1 supports **prime q only**:

| q | n    | pencils | pencil size | notes                     |
|---|------|---------|-------------|---------------------------|
| 2 | 12   | 9       | 4           | sanity test vs BruteForce |
| 3 | 63   | 28      | 9           | fast; default sweep       |
| 5 | 525  | 126     | 25          | `--full` flag             |
| 7 | 2107 | 344     | 49          | `--xlarge`; α expensive   |

Every other `n` raises `ValueError`. Prime-power `q ∈ {4, 8, 9, ...}`
is in principle valid for the construction but needs `F_{p^k}` with
`k > 1`, which v1 doesn't implement. Adding it is ~50 lines of
polynomial-ring code, or a `galois` dependency — defer until someone
asks for `n = 208` (q=4) specifically.

The construction is genuinely sparse on the `n`-line. If you need
coverage at arbitrary `n`, this isn't the search you want.

## What the search actually does

`_run()`:

1. Build `F_{q²}` (small tuple-arithmetic class, ~60 lines).
2. Enumerate PG(2, q²) points (`q⁴ + q² + 1` canonical reps).
3. Filter to the unital `H` (norm sum = 0; `q³ + 1` points).
4. For every unordered pair of unital points, compute the line through
   them, canonicalize, and bucket unital indices by canonical line.
   Each bucket is a secant (size `q+1`); the set of buckets is the
   vertex set; the pencil at a unital point is the set of secants
   containing it. Cost `O(q⁶)`.
5. For each of `top_k` trials: seed `Random(seed*1000 + trial)`, walk
   the pencils, randomly bipartition, emit bipartite edges.

Base class scores each realization by `c_log` and keeps the top_k.
`is_k4_free` is recomputed by base on every returned graph — if it
ever reports `False`, the pencil enumeration or bipartition has a bug.

## Caveats — read before scaling up

### 1. `α` is the bottleneck, not the construction

At `q=5` (`n=525`) the construction finishes in under 0.1 s, but the
graph has ~5000 edges and `alpha_exact_nx` on that can take minutes.
At `q=7` (`n=2107`, ~40k edges) `alpha_exact_nx` is likely infeasible
with the current bitmask branch-and-bound; the driver gates `n=2107`
behind `--xlarge` with a warning.

### 2. Prime-q-only in v1

`q=4, 8, 9, ...` need `F_{p^k}` with `k > 1`, i.e. polynomial-basis
arithmetic over `F_p` for the inner `F_q` itself. Not implemented. Use
prime `q` only.

### 3. The K₄-freeness argument is load-bearing

It rests on Prop 2.ii (pencils share ≤ 1 vertex) and Prop 2.iv (every
`K₄` has 3 vertices in a pencil). If the pencil enumeration ever
changes — e.g. if someone adds support for `q=4` and misidentifies
some pairs as secants — that invariant can quietly break. Base's
`is_k4_free` check on returned graphs is your safety net; keep it
enabled in CI.

### 4. Seed semantics

Trial `t` uses `random.Random(seed*1000 + t)`. Same `seed + n + top_k`
⇒ identical edge sets (byte-equal). `top_k` larger than 1 gives you
independent realizations; `c_log` is non-deterministic in `top_k`
because the graph is non-deterministic.

## When to reach for it

- Benchmarking a new search at `n ∈ {12, 63, 525}`.
- Citing an explicit construction in a notebook or writeup ("SAT beats
  the best explicit Ramsey construction by 2× in this range").
- Verifying the theoretical lower-bound order at moderate `n`.

## When **not** to reach for it

- You want to win `c_log` — Hq* won't.
- Arbitrary `n` — prime-q-only means huge gaps between supported sizes.
- `n ≥ 2107` with the current α implementation — time-infeasible.
- You want a deterministic graph — it's randomized; you'll get a
  slightly different `c_log` per seed.

## Open questions

1. Does `--xlarge` finish if `alpha_exact_nx` is swapped for an
   SAT-based α computation in the base class? At `n=2107` the density
   is moderate (~2%) — might be tractable.
2. Prime-power q=4 (`n=208`) is the most interesting missing size — it
   sits between 63 and 525. Worth the `F_4` arithmetic extension?
3. Does post-processing `Hq*` with an α-reducing heuristic (edge
   flipping, pencil re-bipartitioning conditioned on α) meaningfully
   close the gap to SAT's best at `n=63, 525`? The paper is silent on
   this — it's about asymptotics, not finite optimization.
