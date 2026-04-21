# `BruteForce` — exact enumeration via nauty `geng`

## What it does

Streams **every non-isomorphic K₄-free graph** on `n` vertices by piping
`geng -k n` (nauty's graph generator) and parsing the graph6 output.
Base class scores each and keeps the top_k by `c_log`.

The `-k` flag is geng's "K₄-free" filter, so every yielded graph is
guaranteed K₄-free — no validity check needed at our level. No
randomness, no heuristics; same run → same output every time.

## Why it's useful

At `n ≤ 10` this gives **ground truth**. For every degree sequence, the
best possible `c` at that `n` is exactly what `BruteForce` finds. Every
other search (circulants, random, SAT warm-starts, LLM loops) is
validated against this baseline — if a method can't match `BruteForce`'s
best at small `n`, its scoring pipeline is wrong.

It also populates `graphs/brute_force.json` with the canonical small-N
catalog that downstream consumers (visualizer, leaderboards, β-test
constructions) depend on.

## Scope and hard limit

`geng` output grows very fast:

| n  | K₄-free graphs | time |
|----|----------------|------|
| 7  | ~850           | <1 s  |
| 8  | ~12 k          | <1 s  |
| 9  | ~274 k         | ~2 s |
| 10 | ~12 M          | ~1 min |
| 11 | ~1 B           | infeasible |

Past `n = 10` the enumeration is infeasible on a single machine, which
is why every other search in this folder exists.

## Prerequisites

`geng` must be on `PATH` or findable by `utils.nauty.find_geng`. If
it's not, the search logs an error event and returns `[]` — it will
**not** crash the caller. Build it via `scripts/setup_nauty.sh` or use
the micromamba `k4free` env (ships nauty).

## What the class doesn't do

- **No constraints.** `BruteForce` takes only `top_k`. It does not
  accept `d_max`, `alpha`, `is_regular`, etc. — if you want to
  enumerate a constrained subspace, filter the returned results in the
  caller, or write a new class that uses different `geng` flags.
- **No streaming top_k.** Every graph is held in memory until the base
  class sorts. For `n = 10` this is 12M graphs — expect memory
  pressure. If this becomes a problem, the right fix is a priority
  queue in `_run()` that evicts as it goes; current code assumes
  `n ≤ 9` is the common case.

## When to reach for it

- Validating a new search at small `n`.
- Rebuilding `graphs/brute_force.json`.
- Answering exact-α questions for `n ≤ 10`.
- Sanity-checking Ramsey-style lower bounds (e.g. `R(4,3) = 9` should
  fall out of a brute-force sweep on `n = 8` vs `n = 9`).

## When **not** to reach for it

- `n ≥ 11`. Pick a different search.
- You only care about one extremal graph per `n`; a constrained search
  (circulant, SAT with `α`/`d_max` targets) is orders of magnitude
  faster even when brute-force is feasible.
