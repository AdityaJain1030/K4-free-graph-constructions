# `experiments/greedy/`

Re-implementations of the original greedy / random K4-free constructions
on top of the `EdgeFlipWalk` template (the active engine after
`RandomWalkSearch` was retired). Each is a thin policy specification
(score function + proposer filter) — the search engine, validity
maintenance, and softmax/argmax selection are all shared.

This folder is a sanity check + reference: by expressing different
searches as policies over a common engine we get cheap correctness
verification (K4-freeness, no-double-edge, etc. enforced once in
`EdgeFlipWalk`) and an easy comparison surface.

## Files

| Script | Original class | Policy as a one-liner |
|---|---|---|
| `random_capped.py` | `search.RandomSearch` (deleted) | uniform over legal adds with `deg(u), deg(v) < d_cap` |
| `regularity.py` | `search.RegularitySearch` (deleted) | greedy on `−(d_u + d_v)`, β=∞ |
| `regularity_alpha.py` | `search.RegularityAlphaSearch` (deleted) | greedy on `−(d_u + d_v)` with periodic α-stagnation intervention |

All three:
- Use add-only walks (proposer filters to `is_add=True`).
- Sweep the same default cap list `{3, 4, 5, 6, 8, 10, 12, 15, 20}` clipped to `[1, n-1]`.
- Halt at cap-saturation (`max_consecutive_failures=1`, walk fails when no
  K4-safe add with both endpoints under cap exists).
- Use the validity-mask incremental K4 check from `EdgeFlipWalk` —
  no per-step global K4 verification.

## Mapping notes

### `random_capped.py`
The original `RandomSearch` did a two-pass shuffled-greedy build over
the (u,v) pair list, accepting an edge iff K4-safe and both endpoints
were below the cap. The walk port produces the same outputs in
distribution: `propose_from_valid_moves_fn` filters the K4-safe valid
set to add-only edges with `deg < d_cap` on both endpoints, then the
walk's default uniform sampler picks one. When the filtered set is
empty the walk halts — same termination rule.

### `regularity.py`
The original `RegularitySearch` greedily picked the add that minimised
the post-add degree variance. Up to a monotone transform that's the
same as `−(d_u + d_v)` (a smaller endpoint-sum = less variance bump
from the move). The walk port uses `batch_score_fn = score_neg_d_sum`
and `beta = float("inf")` for greedy argmax.

`add_edges_weighted.py --weight d_min` is the same scorer at finite β
— softer; this script is the β=∞ limit.

### `regularity_alpha.py`
The original `RegularityAlphaSearch` ran regularity scoring most of
the time but periodically probed α and intervened when it stagnated.
The port reproduces this with a closure-state scorer:

- Every `--alpha-check-every` steps, sample `alpha_lb(adj)`.
- If the last `--stagnation-window` α samples all match-or-exceed the
  preceding samples (no strict decrease over the window), the *next*
  step's score switches to `−alpha_lb(post-add) − 0.05·(d_u + d_v)`.
- After one intervention the walk reverts to plain regularity scoring.

The α probe uses the greedy lower bound (`utils.alpha_surrogate.alpha_lb`),
not exact CP-SAT — same as the `add_edges_weighted` α scorer. Cost is
~1 ms per probe per N≈30 graph.

## Comparison to other random-baseline files

| | `random/add_edges.py` | `greedy/random_capped.py` | `random/add_edges_weighted.py --weight d_min` | `greedy/regularity.py` |
|---|---|---|---|---|
| stop | edges / d_max / α target | cap-saturation | edges / d_max / α / saturation | cap-saturation |
| candidate filter | adds only | adds only with `d<cap` | adds only | adds only with `d<cap` |
| score | uniform | uniform | softmax `−(d_u+d_v)` | greedy argmax `−(d_u+d_v)` |
| β | — | — | 4 (default) | ∞ |

So `greedy/regularity.py` is the **β=∞ + cap** specialisation of
`add_edges_weighted.py --weight d_min`.

## What replaced what

| Old class | Old driver | Current implementation |
|---|---|---|
| `RandomSearch` | `RandomWalkSearch` policy | `experiments/greedy/random_capped.py` |
| `RegularitySearch` | `RandomWalkSearch` policy | `experiments/greedy/regularity.py` |
| `RegularityAlphaSearch` | `RandomWalkSearch` policy | `experiments/greedy/regularity_alpha.py` |
| (n/a) | `RandomWalkSearch` itself | retired; use `EdgeFlipWalk` directly |

## Status

Newly ported (2026-04-27) after `RandomWalkSearch` and the original
`experiments/greedy/` were retired. Behaviour matches the policy
descriptions of the deleted classes; numerical values may differ
slightly from earlier runs because the underlying engine
(EdgeFlipWalk) maintains its valid-mask incrementally rather than
the stateful `RandomWalkSearch` mask, and softmax sampling RNG
streams are not byte-identical across engines.
