# `RegularitySearch` — greedy degree-variance minimization

## What it does

For each `d_cap` in a sweep (default `{3, 4, 5, 6, 8, 10, 12, 15, 20}`
clipped to `min(20, n//2)`), build one graph greedily:

1. Find all vertices below `d_cap`. Pick the subset within `+1` of the
   current minimum degree (widen to the full below-cap set if that
   subset has fewer than 2 vertices).
2. Among unordered pairs in that subset, score each candidate edge by
   the **degree variance that would result from adding it** — after
   tentatively adding it and confirming K₄-freeness. Pick the minimizer.
3. Commit the edge. Repeat until no edge can be added.

The filter to "low-degree vertices only" keeps the candidate set small
(most pairs don't help variance anyway), and the variance objective
pulls the degree sequence toward regularity.

Ported from the `method3` baseline in
`funsearch/experiments/baselines/run_baselines.py`.

## Why it exists

1. **Structural baseline.** `RandomSearch` chooses edges uniformly;
   this one chooses edges to flatten the degree sequence. Comparing
   the two shows whether *regularity by itself* — no α signal — is
   worth anything for minimizing `c_log`.
2. **Seed generator for near-regular SAT.** `search/sat_regular.py` pins
   degrees to a single `D`. The output of this search is a cheap,
   near-regular K₄-free graph that can be fed in as a warm start.
3. **Ablation partner for `regularity_alpha`.** The `method3b` /
   `method4` variants add α awareness on top of this. Keeping the
   pure-regularity version as its own class isolates that delta.

## What to expect from it

On the baselines sweep (N=6..20) it plateaued at c ≈ 0.99, essentially
tied with its α-aware variants — the α signal didn't buy anything over
plain degree balancing. It does beat the α-blind random baseline
(c ≈ 0.96 vs 0.99... wait, the numbers flip: `method1` random won at
0.956, `method3` sat at 0.990). In other words **random-with-cap beats
greedy regularity on this range.** That's the kind of result this
search exists to produce — a clean negative that closes a direction.

## Caveats

### 1. Greedy, no backtracking

Once an edge is committed it stays. If an early edge forces later
choices into a bad region, the search has no way to recover. Variance
minimization happens to play well with this (it's convex-ish on the
degree sequence), but there is no guarantee of optimality at a fixed
`d_cap`.

### 2. `is_k4_free` rebuilds bitmasks every call

Same caveat as `RandomSearch`: each tentative edge does an O(n²)
adjacency→bitmask rebuild inside `is_k4_free`. For an O(n²) candidate
set per edge and O(n·d_cap) edges, this is O(n⁵ d_cap) worst case. Fine
for `n ≤ 30`; at larger `n`, lift `would_create_k4` out of
`funsearch/experiments/baselines/run_baselines.py` into `utils/` and
maintain the bitmasks incrementally.

### 3. Degree-cap choice dominates the outcome

The sweep picks the best `c_log` across caps, but the underlying
regularity heuristic is **very** sensitive to `d_cap`. If you pass a
specific `d_max`, make sure you know what you're pinning — this
search does not adjust the cap to rescue itself.

## When to reach for it

- You want a near-regular K₄-free graph as a warm start for a solver.
- You're ablating a more complex method and need the "no α signal"
  control.

## When **not** to reach for it

- You want the lowest `c_log` — random with a degree cap beats this,
  and SAT / circulants crush both.
- `n > 50` — the per-candidate K₄-free check dominates runtime.
