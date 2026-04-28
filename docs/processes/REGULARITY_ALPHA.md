# `RegularityAlphaSearch` — regularity with an α-stagnation trip wire

> **MOVED (twice).** The original `RegularityAlphaSearch` class was
> retired in favour of a `RandomWalkSearch` policy; `RandomWalkSearch`
> was then retired in favour of `EdgeFlipWalk`. The current live
> equivalent is
> [`experiments/greedy/regularity_alpha.py`](../../experiments/greedy/regularity_alpha.py)
> (re-ported on top of `EdgeFlipWalk`, 2026-04-27) — variance-min
> score with closure state for periodic α-stagnation intervention.
> Notes below describe the algorithm for reference.

## What it does

Same greedy as `RegularitySearch` — add the edge that minimizes
post-add degree variance among low-degree below-cap vertices, subject
to K₄-freeness. Additionally:

1. Every `alpha_check_every` edges (default **10**), compute α(G)
   exactly.
2. Track how many edges have been added since α last dropped.
3. If that counter hits `alpha_patience` (default **20**), take **one**
   step with a different heuristic — pick the pair with the most common
   neighbors — then reset the counter and return to degree balancing.

The common-neighbor step is the α-pressure intervention: two vertices
with many shared neighbors are likely to be *together* in a maximum
independent set, and adding the edge between them is often the cheapest
way to knock that IS out.

Ported from the `method3b` baseline in
`funsearch/experiments/baselines/run_baselines.py`.

## Why it exists

This is the ablation partner for `RegularitySearch`. The pure
regularity heuristic is α-blind; this one sneaks α signal in without
fully committing to "pick every edge by α". If α awareness matters,
this should beat `RegularitySearch`; if it doesn't, the comparison
localizes the gap — the common-neighbor intervention isn't enough.

The baselines sweep from funsearch reported essentially a tie
(method3 ≈ 0.9899 vs method3b ≈ 0.9850 averaged over N=6..20). That's
the negative result this search was built to produce.

## What to expect from it

Typically indistinguishable from `RegularitySearch` on the N≤30
overlap — the α check only fires a few times per build and the
common-neighbor step often picks the same edge degree-balancing would
have picked anyway. Small improvements in the 0.01–0.03 range are
normal; bigger swings are a sign of a pathological degree-variance
tie-break, not α awareness working.

## Caveats

### 1. "Every 10 edges" is a coarse control loop

With N=20 and d_cap=5 you get ~50 edges and ~5 α checks. That's a
handful of opportunities for the trip wire to fire — if it fires zero
times, the search degenerates to `RegularitySearch` exactly. The
metadata includes `common_nbr_fires` and `alpha_drops` so you can tell
which regime a particular run actually ran in.

### 2. α is computed exactly via branch-and-bound

We use `utils.graph_props.alpha_exact` (bitmask B&B). For N ≤ 30
this is sub-second per call. Above that, the original `method3b` falls
back to SAT with a 30 s timeout; we don't — if you need this search at
N > 40, wire in a SAT path the same way `funsearch/.../run_baselines.py`
does with `alpha_with_fallback`.

### 3. Common-neighbor step is K₄-checked, not K₄-aware

The heuristic ranks candidates by `|N(u) ∩ N(v)|`, then rejects any
that would create a K₄. If every high-overlap pair is K₄-blocked, the
step falls through to degree balancing rather than failing.

### 4. Only one common-neighbor step per trip

When the patience counter fires, we take *one* common-neighbor step
and then reset. This matches the baseline exactly. A "keep running
common-neighbor until α drops again" variant is a cheap extension but
changes the character of the search.

## When to reach for it

- Comparing "structural" (`RegularitySearch`) to "structural + α"
  greedy heuristics head-to-head.
- As a slightly stronger warm-start generator than `RegularitySearch`
  when you want every bit of c you can get before handing off to SAT.

## When **not** to reach for it

- You want pure regularity signal — use `RegularitySearch`.
- You want optimal α-suppression — that's SAT, not a greedy.
- `n > 40` without a SAT fallback wired in — `alpha_exact` will start
  to matter in the inner loop.
