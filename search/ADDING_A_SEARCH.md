# Adding a new search to `search/`

`DESIGN.md` is the spec. This file is the playbook — how to write a
new `Search` subclass that lands well with the existing code.

Read it before opening a new file under `search/`. It's opinionated
on purpose — the point of the folder is that every search looks the
same from the outside.

---

## The one thing every new search should do

Produce graphs. Return them. Nothing else.

```python
class MySearch(Search):
    name = "my_search"

    def _run(self) -> list[nx.Graph]:
        graphs = ...   # construct however
        return graphs
```

Timing, scoring (α, d_max, c_log, K₄-freeness), logging, persistence,
top_k truncation — all handled by the base class. If you find
yourself writing any of those in `_run()`, stop and look at how
`CirculantSearch._run()` and `BruteForce._run()` stay terse.

---

## Checklist

Go through this before calling it done:

1. **One file.** `search/<name>.py`. No sub-packages. Shared helpers go
   in `utils/`, not `search/`.
2. **`name` attribute** set on the class. This string becomes:
   - the `source` tag in `graph_db`,
   - the prefix of the log filename,
   - the `algo` field on every `SearchResult`.
   Pick something short and kebab-or-snake-free: `random`, `circulant`,
   `brute_force`, `sat_warmstart`. Not `MySearch` and not
   `my-cool-search-v2`.
3. **`_run()` returns `list[nx.Graph]`.** Up to `self.top_k` elements
   after sorting is ideal, but returning more is fine — base will
   truncate. Returning fewer is fine too. Returning `[]` is fine.
4. **Lean on `utils/graph_props.py` for validity and scoring inside
   `_run()`** when you genuinely need them mid-construction (e.g.
   rejection in a greedy build). Don't reimplement K₄-detection or
   α — if the existing helper is too slow, extend `utils/`, don't
   duplicate.
5. **Kwargs on `__init__` are the API.** Every constraint your
   algorithm supports is an `__init__` kwarg, stored as `self.<name>`,
   passed up via `super().__init__(..., <name>=<name>)`. The kwargs
   auto-appear in the `search_start` log line, so every run is
   self-describing.
6. **Reuse the shared vocabulary** from `DESIGN.md` for kwarg names:
   `alpha`, `d_max`, `is_regular`, `girth_min`, `seed`, `iters`,
   `timeout_s`, `connection_set_size`. Only invent a new kwarg when
   none of the existing ones mean what you want.
7. **Document hard vs soft for each kwarg.** Does the constraint go
   into the model and no returned graph can violate it (hard), or is
   it a target / cap / bias (soft)? The class docstring must say.
   Base does not enforce — callers compare.
8. **Call `self._stamp(G)` at the moment of discovery** if you care
   about per-graph `time_to_find` beyond coarse total elapsed.
9. **Attach algo-specific metadata** via `G.graph["metadata"] = {...}`.
   Base forwards it verbatim into the `SearchResult` and into
   `graph_db` on save. Examples: connection set, solver params,
   mutation lineage, trial / seed indices.
10. **Use `self._log(event, level=N, **kv)`** for custom events. Pick
    the verbosity level according to the table in `DESIGN.md`
    (`1 = attempt/infeasible/timeout`, `2 = iteration/move`,
    `3 = full trace`). Base's `search_start` / `search_end` /
    `new_best` / `error` events fire automatically — do **not**
    re-emit them.
11. **Export the class** in `search/__init__.py`. One line added,
    one entry in `__all__`.
12. **Write a driver in `scripts/run_<name>.py`** that instantiates
    the search under an `AggregateLogger`, runs it, prints a small
    summary table, and calls `search.save(results)` if you want the
    results persisted. Model it on `scripts/run_random.py`.
13. **Write a short markdown doc under `docs/searches/<name>.md`**
    (upper-case filename; if your search has variants, group them
    under `docs/searches/<family>/`, e.g. `docs/searches/circulant/`).
    Explain: the intuition, when to use it, when not to, the
    non-obvious failure modes. Don't duplicate `search/DESIGN.md`.

---

## Common mistakes (don't)

- **Timing yourself.** `time.time()` inside `_run()`, `dt = ... - t0`,
  printing elapsed. Base already does all of this. The only place
  you call `time` is through `self._stamp(G)`.
- **Computing `c_log` inside `_run()`.** Base computes it on every
  returned graph. If you compute it for *scoring during search*
  (e.g. greedy picks the edge that minimizes `c` so far), that's
  fine — but don't also return it; let base wrap the result.
- **Filtering out non-K₄-free results silently.** Return them with
  whatever they are — base records `is_k4_free` on the result. The
  caller decides whether to drop them. Silent filtering hides bugs
  in your construction.
- **Opening log files directly.** Only `self._log(...)`.
- **Calling `GraphStore` directly.** Only `self.save(results)`.
- **Guessing at verbosity.** If you're not sure what level an event
  should be, start at `level=1` (a per-stage coarse event) — `0` is
  reserved for base's lifecycle events and writes unconditionally.
- **Returning a flat `list` of arbitrary graph types.** Must be
  `nx.Graph` instances. If you're producing numpy adjacency
  matrices internally, convert via `nx.from_numpy_array` at the end.
- **Special-casing empty / tiny graphs.** Base handles `n = 0` and
  degenerate inputs — produces `c_log = None` and moves on. Don't
  raise in `_run()` for uninteresting inputs.

---

## Deciding what goes in `utils/` vs `search/`

If two search classes would need the same helper (e.g. "incremental
K₄-free check with a maintained neighborhood bitmask"), it belongs in
`utils/`. If the helper is meaningful only within one algorithm (e.g.
"enumerate connection sets for a circulant"), it stays inside the
search's file as a private `_func`.

Don't pre-factor. Write the new search self-contained, ship it, and
only hoist a helper to `utils/` when the second caller appears.

---

## Testing a new search

At minimum:

- `MySearch(n=6).run()` completes and returns something (or `[]`
  with a logged reason).
- At `n` small enough that `BruteForce` works, your best `c_log`
  should be **≥** `BruteForce`'s best. If it's less, your scoring
  is wrong — there's nothing a constrained search can find that an
  exhaustive search can't.
- Re-running the same instance with the same `seed` (if your search
  is randomized) gives the same result. If it doesn't, you're
  reading uninitialized RNG state somewhere.

`scripts/test_search.py` is the existing smoke harness — mirror its
shape for your driver.

---

## Comparing against existing searches — don't re-run them

Every non-SAT search (`brute_force`, `circulant`, `cayley`, `regularity`,
`random`, `mattheus_verstraete`, …) has already been swept and its
results are cached in `graph_db`. **Do not re-run those searches to
benchmark against them.** Query the DB instead:

```python
from graph_db import DB

with DB() as db:
    # best c_log at each n, across every existing source
    baseline = {r['n']: r for r in db.frontier(by='n', minimize='c_log')}

    # or: best from a specific competitor
    bf = {r['n']: r['c_log']
          for r in db.frontier(by='n', minimize='c_log', source='brute_force')}
```

Or from the shell for a quick sanity check:

```bash
python scripts/db_cli.py query --source brute_force \
    --columns n,c_log,alpha,d_max --top 20

python scripts/db_cli.py query --n 17..22 --top 5   # overall frontier
```

The SAT/ILP results aren't in `graph_db` yet (they still live under
`reference/pareto/`), so those are the only benchmarks that
still require reading from disk directly.

See `graph_db/USAGE.md` for the full query surface.
