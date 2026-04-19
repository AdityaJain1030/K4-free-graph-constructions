# `RandomSearch` — degree-capped random edge addition

## What it does

For each `d_cap` in a sweep (default `{3, 4, 5, 6, 8, 10, 12, 15, 20}`
clipped to `min(20, n//2)`), run `num_trials` (default 3) independent
trials. A trial shuffles every vertex pair and walks the list twice;
each pair is added iff

1. both endpoints are below `d_cap`, and
2. adding it keeps the graph K₄-free.

The second pass handles pairs that were initially cap-blocked but
become addable once the cap-blocking pair itself gets rejected later.
Every survivor is returned; the base class keeps the top_k by `c_log`.

Ported from the `method1` baseline in
`funsearch/experiments/baselines/run_baselines.py`.

## Why it exists

Three reasons, in order:

1. **Control baseline.** Any new construction method needs to beat
   "shuffle edges, cap degree, reject K₄s." If it doesn't, the
   method isn't finding structure — just slowly rediscovering
   noise.
2. **Cheap seed generator.** Random edge-addition produces plausibly
   K₄-free, plausibly regular-ish graphs in milliseconds; downstream
   metaheuristics (SA, tabu, LLM loops) can warm-start from these
   instead of the empty graph.
3. **Sanity check for the scoring pipeline.** If `c_log` on random
   graphs comes out wildly different from the funsearch baseline's
   numbers, something in the pipeline is wrong.

## What to expect from it

Random plateaus around **c ≈ 0.95 ± 0.1** across `n ∈ [10, 30]`.
That's far from the Paley-17 benchmark of **c ≈ 0.68** and noticeably
worse than anything structured (circulants, SAT-optimal frontier,
block joins). The gap is the whole point: an adversarial graph needs
*symmetry*, and uniform shuffling destroys it.

If a new heuristic lands in the 0.9s on this range, it's barely
beating random, which usually means the heuristic is dominated by
its K₄-free rejection step and isn't actually steering the search.

## Caveats

### 1. "Random" means the outcome distribution, not a uniform sample

The shuffle-then-walk procedure does **not** sample uniformly from
K₄-free graphs at a given degree cap. The order of addition biases
toward dense early regions of the pair list. That bias is what the
second pass partially corrects — but only partially. If you need a
uniform sample for some statistical argument, don't use this; use
rejection sampling or a dedicated random-graph generator.

### 2. Two passes, not a fixed point

A third pass would add more edges in some cases; we stop at two to
keep the construction fast. A "run until saturated" variant is a
cheap extension if you want max-density K₄-free random graphs — it
just won't change `c` much because α tracks density roughly
log-linearly.

### 3. Seed is coarse

The base seed combines as `seed * 1000 + trial * 100 + d_cap`. With
three trials across a 9-cap sweep you get 27 distinct RNG streams
per `n`, which is fine for a control baseline but will miss the
long tail of rare favorable shuffles. If you want many more trials,
bump `num_trials` — cost is linear.

### 4. Validity check runs after every tentative add

`is_k4_free(adj)` rebuilds bitmasks each time rather than maintaining
them incrementally. That's O(n²) per check, O(n²) tentative adds, so
O(n⁴) per trial. Fine for `n ≤ 30`; at larger `n` this becomes the
dominant cost and is worth making incremental — compare to the
`would_create_k4` helper in `funsearch/experiments/baselines/run_baselines.py`
which maintains the bitmasks inline.

## When to reach for it

- Benchmarking a new search against a no-structure baseline.
- Generating a starting population for a metaheuristic loop.
- Producing a quick K₄-free graph on up to ~30 vertices when you
  don't care about optimality.

## When **not** to reach for it

- You want a structured or near-optimal graph — use `CirculantSearch`
  or the SAT solver.
- You want a uniform sample — the procedure is biased.
- `n > 50` — validity check becomes the bottleneck and the attractor
  `c` value won't budge.
