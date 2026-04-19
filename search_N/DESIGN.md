# search_N — Technical Design

## Goal

Give every "find a K₄-free graph on N vertices" algorithm — brute force,
circulant enumeration, SAT warm-start, tabu, LLM-loop — a **single
contract** to plug into, so the rest of the pipeline (logging, timing,
scoring, validity checks, persistence into `graph_db`) is shared and
each new algorithm is just its own construction routine.

One folder full of constructions. Nothing else.

## Non-goals

- Not a generic optimization framework. The objective is fixed:
  `c_log = α(G) · d_max / (N · ln d_max)`, minimize.
- Not a scheduler / experiment tracker. Orchestration (running the
  same search across many N, or many searches for one N) lives in
  `scripts/`.
- Not responsible for bounding N. Algorithms advertise no hard limits;
  the caller decides what N values to invoke with.
- Not a graph persistence layer. `graph_db` is. Searches hand off to
  it on request.

---

## The `Search` contract

Every concrete search is a subclass of `Search` that does one thing:
produce candidate `nx.Graph` objects on `self.n` vertices. Everything
else — timing, scoring, validity checks, logging, persistence —
comes from the base class.

### What the subclass writes

```python
class MySearch(Search):
    name = "my_search"   # source tag in graph_db and log filename prefix

    def _run(self) -> list[nx.Graph]:
        # produce up to self.top_k graphs on self.n vertices
        ...
        return graphs
```

Inside `_run()` the subclass may:

- Read `self.n`, `self.top_k`, `self.verbosity`.
- Call `self._log(event, level=..., **kv)` to emit algorithm-specific
  events (SAT's `attempt`/`infeasible`, tabu's `iteration`, etc.).
- Call `self._stamp(G)` at the moment of discovery to record an
  accurate per-graph `time_to_find`. If it doesn't, base fills
  `time_to_find` with total elapsed at return time.
- Attach algorithm-specific payload via `G.graph["metadata"] = {...}`
  (connection set, solver params, mutation lineage, etc.). Base
  forwards this dict verbatim into the result's `metadata` field.

The subclass **does not**:

- Time itself, compute `c_log`, compute `α`, or check K4-freeness.
- Open log files, pick log paths, or tee to aggregate logs.
- Call `GraphStore` or `graph_db` directly.

### Why no `multi_result` flag

Dropped. Every search can return 1 or K results — the only question is
what the caller asked for via `top_k`. Algorithms that structurally
produce one graph return a one-element list regardless and say so in
their docstring. One knob, not two.

### Per-algorithm constraints

`n` is the only mandatory constructor argument. Every search also
accepts the universal triad `top_k`, `verbosity`, `parent_logger`.
Beyond that, each subclass advertises **its own constraints** via its
`__init__` signature — these shape what the search is asked to find.

```python
class MySearch(Search):
    name = "my_search"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger: "AggregateLogger | None" = None,
        # subclass-specific constraints:
        alpha: int | None = None,                 # α(G) target
        d_max: int | None = None,                 # max-degree target
        is_regular: bool = False,
        connection_set_size: int | None = None,   # circulant: |S| == k
        seed: int | None = None,                  # RNG seed
        timeout_s: float | None = None,           # per-instance wall clock
        **kwargs,
    ):
        super().__init__(n, top_k=top_k, verbosity=verbosity,
                         parent_logger=parent_logger, **kwargs)
        self.alpha = alpha
        self.d_max = d_max
        self.is_regular = is_regular
        ...
```

The subclass's `__init__` *is* the declaration of what the algorithm
supports. `BruteForce` accepts only `top_k`; `CirculantSearch` adds
`connection_set_size`, `is_regular`; SAT-style searches add `alpha`,
`d_max`, `timeout_s`; metaheuristics add `seed`, `iters`,
`tabu_tenure`. Nothing is centrally registered — callers read the
subclass's signature or docstring.

**Convention on names.** Reuse the same kwarg across algorithms when
the meaning is the same, so consumers can swap one search for another
without relearning the API:

| Kwarg                         | Meaning                                        |
|-------------------------------|------------------------------------------------|
| `alpha`                       | Require `α(G) == alpha` exactly                |
| `alpha_min`, `alpha_max`      | Require `α(G)` in `[alpha_min, alpha_max]`     |
| `d_max`                       | Require max-degree equals this exactly         |
| `d_max_min`, `d_max_max`      | Require max-degree in range                    |
| `is_regular`                  | Require a regular graph (`d_min == d_max`)     |
| `girth_min`                   | Require `girth(G) >= girth_min`                |
| `connection_set_size`         | Circulant: `|S| == k`                          |
| `seed`                        | RNG seed for randomized algorithms             |
| `iters`, `timeout_s`          | Search budget (iterations / wall clock)        |

Subclasses are free to add their own — the table above is the
**shared vocabulary**, not the full universe.

**Hard vs soft.** Whether a constraint is enforced on the output or
merely used as a *target* for the search is the subclass's call:

- **Hard** — the constraint goes into the model and no returned graph
  can violate it. Example: CP-SAT with `alpha=3` as a model clause.
- **Soft** — the constraint biases the search (scoring, seeding,
  filtering during iteration) but the final best-found graph may miss
  it. Example: a tabu search with `alpha=3` as a scoring target.

Each subclass's docstring must say **per kwarg** whether it's hard or
soft. Base neither enforces nor filters — it simply computes `alpha`,
`d_max`, etc. on every returned graph, and the consumer compares
against the constraint if they need strictness.

**Constraints auto-appear in the log.** Every kwarg the subclass
declares (beyond the universal triad) is stashed on the instance and
forwarded into the `search_start` event, so every run's log is
self-describing:

```
[HH:MM:SS.mmm] SEARCH_START   top_k=5  verbosity=1  alpha=3  is_regular=1
```

No manual logging call needed.

---

## `SearchResult` — the return type

`run()` returns `list[SearchResult]`, one entry per candidate graph.

```python
@dataclass(frozen=True)
class SearchResult:
    G:            nx.Graph
    n:            int
    algo:         str              # source tag (= owning search's `name`)
    c_log:        float | None     # None iff d_max <= 1
    alpha:        int
    d_max:        int
    is_k4_free:   bool             # computed, NOT enforced — see below
    time_to_find: float            # seconds from search_start to discovery
    timestamp:    str              # ISO-8601 UTC, when discovered
    metadata:     dict             # algorithm-specific, from G.graph["metadata"]
```

The subclass returns bare graphs; base computes every field and packs
them into `SearchResult`.

### K4-freeness is checked, not enforced

Base computes `is_k4_free` on every candidate and stores it on the
result. It does **not** filter non-K4-free graphs out.

Rationale: in small / near-regular / LLM-generated searches, the
interesting question is sometimes *"produce many graphs; how close to
K4-free are they?"* or *"enough of them are K4-free"*. Filtering
silently would hide that. Consumers that require K4-freeness filter on
`result.is_k4_free`; consumers that don't, don't. Base stays neutral.

### Saving is opt-in

`run()` returns results to the caller. Nothing is persisted until the
caller asks:

```python
results = MySearch(n=20, top_k=5).run()
# inspect, filter, or discard ...
search.save(results)                              # save all
search.save([r for r in results if r.is_k4_free]) # save a subset
search.save(results[0])                           # save one
```

`save()` routes each `SearchResult` into `graph_db` under
`source=self.name`, with the result's `metadata` attached to the
record. No computation happens here — `graph_db.sync()` populates the
cache afterwards. Callers that only wanted a look at the results (a
dry run, a validation script) simply don't call `save()`.

---

## Verbosity

Every `Search` instance has `self.verbosity: int` (default 0). Base
events always fire; subclass events are gated.

```python
self._log(event, level=N, **kv)   # written iff verbosity >= N
```

Suggested levels:

| Level | Emitted                                                            |
|-------|--------------------------------------------------------------------|
| `0`   | `search_start`, `search_end`, `new_best`, `error` (base only).     |
| `1`   | + coarse per-stage events: `attempt`, `infeasible`, `timeout`.     |
| `2`   | + inner-loop events: `iteration`, `move`, `candidate`, `restart`.  |
| `3`   | + full trace (every solver callback, every mutation, …).           |

Subclasses pick the level for each event; `Search._log` does the
filtering. Base's four lifecycle events are unconditional — they're
how you tell whether anything ran at all.

Instantiate with `MySearch(n=..., verbosity=2)`, or flip at runtime
via `search.verbosity = 2`.

---

## Logging

### One file per run

```
<repo>/logs/search_N/<name>_n<N>_<YYYYMMDD_HHMMSS>.log
```

Line format:

```
[HH:MM:SS.mmm] EVENT_NAME   key=value  key=value  ...
```

### Joining loggers across runs

An orchestration script that runs many searches (e.g. BruteForce for
n=6..10, or three different algorithms on n=20) gets:

1. One per-run log file as usual.
2. One **aggregate** log file that receives every line from every
   child run, prefixed with the owning run's identifier.

API:

```python
from search_N import AggregateLogger, BruteForce, CirculantSearch

with AggregateLogger(name="sweep") as agg:
    for n in range(6, 11):
        BruteForce(n=n, top_k=1, parent_logger=agg).run()
    CirculantSearch(n=20, top_k=5, parent_logger=agg).run()
```

`AggregateLogger` opens a single file
`logs/search_N/<name>_<timestamp>.agg.log`. Every child run, on every
`self._log(...)`, writes one line to its own file *and* one line to
the aggregate with a `[<algo>_n<N>]` prefix appended to the event
column:

```
# per-run file (brute_force_n6_20260418_183012.log):
[18:30:12.145] SEARCH_START   top_k=1  verbosity=0
[18:30:12.812] NEW_BEST       c_log=0.910239  time_to_find=0.66
[18:30:12.814] SEARCH_END     status=ok  n_results=1  elapsed_s=0.67

# aggregate file (sweep_20260418_183012.agg.log):
[18:30:12.145] SEARCH_START  [brute_force_n6]   top_k=1  verbosity=0
[18:30:12.812] NEW_BEST      [brute_force_n6]   c_log=0.910239  time_to_find=0.66
[18:30:12.814] SEARCH_END    [brute_force_n6]   status=ok  n_results=1  elapsed_s=0.67
[18:30:12.820] SEARCH_START  [brute_force_n7]   ...
```

Both files are complete records of the run. The per-run file is
convenient for zooming into one algorithm; the aggregate is convenient
for diffing runs against each other or eyeballing the sweep as a
whole.

Nesting is flat — child loggers only tee into their immediate parent.
An orchestration script that wants a two-level hierarchy (sweep → per-N
bundle → per-algo leaf) composes two `AggregateLogger`s, the outer
passed as `parent_logger` to the inner.

### Standard events

| Event          | Fields                                                     | Emitter |
|----------------|------------------------------------------------------------|---------|
| `search_start` | `top_k`, `verbosity`, subclass kwargs                      | base    |
| `search_end`   | `status`, `n_results`, `best_c_log`, `elapsed_s`           | base    |
| `new_best`     | `c_log`, `alpha`, `d_max`, `time_to_find`, `is_k4_free`    | base    |
| `error`        | `exc` (str of exception)                                   | base    |

Algorithm-specific events are free-form (`attempt`, `iteration`,
`infeasible`, `restart`, …) and must pass a `level=` on `self._log`
so verbosity filtering works.

---

## Control flow

```
                    scripts/run_my_search.py
                              │
                              ▼
              MySearch(n=..., top_k=..., verbosity=...,
                      parent_logger=...)
                              │
                              │ .run()
                              ▼
          ┌───────────────────────────────────────┐
          │ Search.run() — the wrapper            │
          │                                       │
          │  _start_time = now                    │
          │  _log("search_start", ...)            │
          │                                       │
          │     ┌──────────────────────────┐      │
          │     │  subclass._run()         │      │
          │     │   returns list[nx.Graph] │      │
          │     └──────────┬───────────────┘      │
          │                │                      │
          │  for each G:                          │
          │    compute (alpha, d_max, c_log,      │
          │             is_k4_free)               │
          │    read G.graph["metadata"] if any    │
          │    fill time_to_find if unset         │
          │    wrap into SearchResult             │
          │                                       │
          │  sort by c_log, truncate to top_k     │
          │  _log("new_best", ...)                │
          │  _log("search_end", ...)              │
          │  return list[SearchResult]            │
          └───────────────────────────────────────┘
                              │
                              ▼
                     list[SearchResult]
                              │
                    optional .save(results)
                              ▼
                          graph_db
```

`run()` is the only public entry point. `_run()` is never called
directly; the wrapper is what gives the shared behavior.

---

## Module layout

```
search_N/
├── __init__.py        Public surface: Search, SearchResult,
│                      AggregateLogger, concrete classes
├── DESIGN.md          This file
├── base.py            Search (ABC), SearchResult, run() wrapper, helpers
├── logger.py          SearchLogger, AggregateLogger
├── brute_force.py     BruteForce — geng enumeration
├── circulant.py       CirculantSearch — connection-set enumeration
└── ... (future: sat_warmstart.py, tabu.py, evo.py, llm_loop.py)
```

Each concrete search is one file. No sub-packages. If two searches
share a helper, it goes into `utils/`, not `search_N/`.

Logs live at the repo root (`<repo>/logs/search_N/`), not inside this
package. `search_N/` is source code; logs are runtime artifacts.

---

## Integration with `graph_db`

Every search class has a `name` attribute that doubles as:

- the `source` tag in `graph_db`,
- the prefix of its log filename,
- the `algo` field on every `SearchResult` it produces.

`save(results)` is a thin wrapper over `db.add(r.G, source=self.name,
metadata=r.metadata)` for each result. It does not compute properties;
`graph_db.sync()` handles that after the fact.

---

## Adding a new search

1. Create `search_N/<name>.py`.
2. Subclass `Search`, set `name`, implement
   `_run() -> list[nx.Graph]`.
3. Declare any algorithm-specific constraints (`alpha`, `d_max`,
   `seed`, …) as kwargs on `__init__`, document each as hard or soft
   in the class docstring, and store them as instance attributes.
4. For accurate per-graph timing in long runs, call `self._stamp(G)`
   at the moment of discovery.
5. For algorithm-specific metadata, set `G.graph["metadata"] = {...}`.
6. For verbose tracing, use `self._log(event, level=N, **kv)`.
7. Add the class to `search_N/__init__.py`.
8. Add a driver in `scripts/run_<name>.py` that instantiates, calls
   `.run()`, filters/inspects the results, and optionally calls
   `.save(results)`.

No registration, no config file, no framework ceremony.

---

## What this design guarantees

| Property                                        | Mechanism                                   |
|-------------------------------------------------|---------------------------------------------|
| Every result has `c_log`, `alpha`, `d_max`      | Base computes, wraps into `SearchResult`    |
| Every result has `is_k4_free` (checked)         | Base computes; not used as a filter         |
| Every result has `time_to_find` and `timestamp` | Base stamps; subclass may pre-stamp         |
| Uniform logging across all searches             | Base `run()` wraps `_run()`                 |
| Concurrent searches produce joinable logs       | `AggregateLogger` as `parent_logger`        |
| Subclass picks what to log at which verbosity   | `self._log(event, level=N, ...)`            |
| Saving is opt-in and uniform                    | `search.save(results)` → `graph_db`         |
| Subclass stays tiny                             | No plumbing inside `_run()`                 |

## What it does **not** guarantee

- **K4-freeness of results.** Base checks it and stores the flag, but
  does not filter. Consumers that require it filter on
  `result.is_k4_free`.
- **Constraint enforcement.** Subclass-declared constraints
  (`alpha`, `d_max`, `is_regular`, …) are documented hard or soft by
  each subclass. Base does not enforce them on returned results —
  callers compare against the constraint themselves if needed.
- **Non-empty results.** `_run()` may return `[]`; base emits an empty
  `search_end` and returns `[]`.
- **Idempotency.** Randomized or time-limited searches will produce
  different results across runs. `graph_db`'s `(id, source)` dedup
  handles rediscovery.
- **Cross-machine comparability.** `time_to_find` is wall-clock on
  whatever machine ran the search.
- **Concurrent file I/O safety on the aggregate log.** One process
  writing, many child runs sequential inside it, is the assumed model.
  Parallel subprocesses writing into the same aggregate would race.
