# Stochastic Walk — Design Notes

`search/stochastic_walk/walk.py`

---

## What it is

A `Walk` is a stochastic local search over K₄-free graphs. At each step it
proposes a set of candidate moves, filters out invalid ones, scores the
survivors, and picks one via a softmax distribution. It keeps going until the
stopping condition fires or a hard ceiling is reached.

The `Walk` class is abstract and generic over a move type `MoveT`. Subclasses
pin the move shape and implement:

| Method | Required | Responsibility |
|---|---|---|
| `_propose(adj, info, rng, k)` | Yes | Generate up to k candidate moves |
| `_apply(adj, move)` | Yes | Apply the chosen move to adj in-place |
| `_score(adj, move, info, context)` | No | Per-candidate score (default: 0.0) |
| `_score_batch(adj, moves, info)` | No | Batch score (default: delegates to `_score`) |
| `_stop(adj, info)` | No | Halt condition (default: never) |
| `_validate_move(adj, move, info, context)` | No | Single-move validity (default: True) |
| `_validate_move_batch(adj, moves, info)` | No | Batch validity (default: delegates to `_validate_move`) |

Everything else — filtering, softmax selection, termination, multi-trial
loop — lives in the base class and is shared across all walk variants.

---

## Step pipeline

Each step runs:

```
_propose → _filter (_validate_move_batch) → _compute_scores (_score_batch) → _select → _apply
```

**Propose.** `_propose` generates candidates. It may return invalid moves —
the framework will filter them. Returning an empty list counts as a failure.

**Filter.** `_validate_move_batch` filters candidates. By default it calls
`_validate_move` per-candidate with a shared `context` dict (reset to `{}`
once per step). Subclasses can override `_validate_move_batch` directly for
vectorised checks. If no candidates survive, the step is a failure.

**Score.** `_score_batch` scores the valid candidates. By default it delegates
to per-candidate `_score` with the same shared `context` dict. Override
`_score_batch` for vectorised scoring.

**Select.** `_select` draws one candidate from the scored set via softmax with
temperature `beta`. `beta=inf` is greedy argmax with uniform tie-breaking.

**Apply.** `_apply` mutates `adj` in-place. Only called on the selected move.

---

## Propose / validate separation

`_propose` and `_validate_move` are separate methods. This is an engineering
separation, not a statistical one: it lets proposers be cheap and dumb (sample
broadly from the candidate space) while validity logic lives in one place
(`_validate_move`).

Two natural patterns:

1. **Propose a random subset, filter**: `_propose` samples k candidates
   cheaply (possibly including invalids), `_validate_move` filters. Good when
   valid moves are dense and K4 checks are cheap.

2. **Enumerate all valid moves in `_propose`**: `_propose` returns only valid
   moves, `_validate_move` is left as default `True`. Good when the full valid
   set is available cheaply (e.g. from a precomputed mask) and you want
   selection over the exact valid support.

`EdgeFlipWalk` supports both via its `propose_fn` and
`propose_from_valid_moves_fn` hooks respectively.

---

## Context trick

Both `_validate_move` and `_score` receive a `context` dict that is:
- reset to `{}` once per step
- shared across all per-candidate calls within that step

This lets subclasses cache work that is identical for every candidate in a
step — e.g. the current neighbourhood structure or the current α — without
recomputing it per move. For batch variants (`_validate_move_batch`,
`_score_batch`) no context is needed since the call is one-shot.

---

## Termination

The walk terminates on the first of three conditions:

| Condition | Info flag set |
|---|---|
| `_stop(adj, info)` returns True | `info["stopped"] = True` |
| `consecutive_failures >= max_consecutive_failures` | `info["saturated"] = True` |
| `steps >= max_steps` | `info["max_steps_reached"] = True` |

`_stop` is an overridable method, default `return False`. Subclasses or
concrete walk classes wire in whatever objective-based halt condition they need
(e.g. "stop when edges ≥ target" or "stop when α drops below k").

`max_consecutive_failures` and `max_steps` are both absolute step counts —
not n²-derived factors. Both default to finite values and can be set to `None`
to fully disable. Using absolute counts rather than factors makes the threshold
explicit and independent of graph size.

A "failure" is any step where no move was applied — either `_propose` returned
nothing, filtering eliminated all candidates, or scoring/selection found no
winner.

---

## Info dict

The `info` dict is passed to `_stop` and updated every step:

| Key | Meaning |
|---|---|
| `steps` | Total steps taken (accepted + failed) |
| `accepted` | Steps where a move was applied |
| `total_failures` | Steps where no move was applied |
| `consecutive_failures` | Steps since the last accepted move |
| `stopped` | True if `_stop` fired |
| `saturated` | True if `max_consecutive_failures` was hit |
| `max_steps_reached` | True if `max_steps` was hit |

---

## Descriptive names

Every `Walk` requires two string params at construction: `score_fn_name` and
`stop_fn_name`. These are logged in `search_start` so every run is
self-describing. Concrete subclasses either hardcode them (when scoring/stopping
logic is baked in) or re-expose them as their own init params (when logic is
driver-supplied).

---

## Multi-trial loop

`_run` runs `num_trials` independent walks, each with its own RNG seeded as
`seed * 1000 + trial`. Results are collected as a list of `nx.Graph` objects
with metadata attached. The base `Search` class handles scoring, ranking, and
returning the top-k results.

---

## Subclassing

Minimal subclass — only `_propose` and `_apply` are required:

```python
EdgeMove = tuple[int, int, bool]   # (u, v, is_add)

class MyEdgeWalk(Walk[EdgeMove]):
    name = "my_edge_walk"

    def __init__(self, n, *, target_edges, **kwargs):
        super().__init__(n,
            score_fn_name="degree_weighted",
            stop_fn_name="target_edges",
            **kwargs,
        )
        self._target = target_edges

    def _stop(self, adj, info) -> bool:
        return int(adj.sum()) // 2 >= self._target

    def _score(self, adj, move, info, context) -> float:
        u, v, is_add = move
        return float(adj[u].sum() + adj[v].sum())  # prefer high-degree endpoints

    def _propose(self, adj, info, rng, k) -> list[EdgeMove]:
        ...

    def _apply(self, adj, move: EdgeMove) -> None:
        u, v, is_add = move
        adj[u, v] = adj[v, u] = int(is_add)
```

For concrete walk classes that wire in caller-supplied scoring and stopping
(like `EdgeFlipWalk`), `score_fn_name` and `stop_fn_name` are derived from the
supplied callables' `__name__` at init time.
