# Using graph_db for analysis

`graph_db` is not just a backend for the visualizer — it's the sorted,
indexed, typed mirror of every K₄-free graph any solver in this repo has
found. This document shows how to query it from Python and from the CLI.

See `DESIGN.md` for the architecture. See `EXTENDING.md` for how to add
new cached properties.

---

## Opening the DB

```python
from graph_db import DB

with DB() as db:
    ...
```

Defaults: `graphs/` for the JSON store, `cache.db` for the SQLite cache.
Override with `DB(graphs_dir=..., cache_path=...)`.

On open, `auto_sync=True` (default) adds cache rows for any store records
that aren't yet cached. Pass `auto_sync=False` if you are in a script that
will call `db.sync(verbose=True)` explicitly, or if you only want to read.

All methods below are on the `DB` instance.

---

## Inspecting what's there

```python
db.stats()            # totals: n_pairs, n_graphs, n_sources, n_min, n_max, c_min, c_max
db.sources()          # ['brute_force', 'circulant', 'sat_pareto', ...]
db.count(n=17)        # how many rows on 17 vertices
db.count(source='sat_pareto', is_regular=1)
```

---

## Query

`db.query(...)` is the workhorse. Every filter is whitelisted against the
cache schema — no SQL injection surface.

### Shorthand kwargs

Scalar → equality, tuple → inclusive range (either bound may be `None`),
list → `IN (...)`:

```python
db.query(n=17)                              # n == 17
db.query(n=(10, 20))                        # 10 <= n <= 20
db.query(n=(None, 20))                      # n <= 20
db.query(source=['sat_pareto', 'circulant'])  # source IN (...)
db.query(n=17, c_log=(0, 0.75), is_regular=1)
```

### Explicit form

Sometimes you want to keep range filters out of `kwargs` collisions:

```python
db.query(
    where={'n': 17, 'source': 'sat_pareto'},
    ranges={'c_log': (0, 0.75), 'd_max': (4, None)},
    isin={'source': ['sat_pareto', 'circulant']},
    order_by='c_log',         # 'col' = asc, '-col' = desc, list = multi-sort
    limit=10,
)
```

### Useful columns to filter on

| column | meaning |
|---|---|
| `n` | vertex count |
| `m` | edge count |
| `source` | producer tag (`sat_pareto`, `circulant`, `brute_force`, ...) |
| `c_log` | the extremal metric `α·d_max / (n·ln d_max)` — lower is better |
| `alpha` | independence number |
| `d_max`, `d_min`, `d_avg`, `d_var` | degree stats |
| `is_regular`, `regularity_d` | 0/1 and the degree if regular |
| `is_k4_free` | 0/1 |
| `girth`, `diameter`, `radius` | standard integer invariants |
| `n_triangles`, `clique_num`, `greedy_chromatic_bound` | |
| `spectral_radius`, `spectral_gap`, `algebraic_connectivity` | |
| `turan_density`, `beta` | derived scalars |

The full whitelist is available via `db.schema_columns()`.

### Convenience methods on top of query

```python
db.top('c_log', k=10, ascending=True, n=(17, 25))
# 10 best c_log in the n-range

db.frontier(by='n', minimize='c_log', source='sat_pareto')
# One row per distinct n — whichever has the minimum c_log

db.get(graph_id, source)          # one row
db.get_all(graph_id)              # all (source)-flavours for one graph
```

---

## Going from a row to the graph

Cache rows are scalars and JSON blobs only — no graph object. Hydrate on
demand:

```python
rec = db.query(n=17, c_log=(None, 0.7), limit=1)[0]
G   = db.nx(rec['graph_id'])           # networkx.Graph
adj = db.adj(rec['graph_id'])          # numpy uint8 adjacency
s6  = db.sparse6(rec['graph_id'])      # canonical sparse6 string
```

Or hydrate a list in one shot (the visualizer's pattern):

```python
rows_with_graphs = db.hydrate(db.query(n=(10, 20), order_by='c_log'))
# each row now also has 'G', 'adj', 'sparse6' keys alongside the scalars
```

---

## Worked examples

### Best graph we've ever found per vertex count

```python
from graph_db import DB
with DB() as db:
    for r in db.frontier(by='n', minimize='c_log'):
        print(f"n={r['n']:2d}  c_log={r['c_log']:.4f}  "
              f"source={r['source']:12s}  id={r['graph_id'][:10]}")
```

### Rediscovery report: which graphs were found by ≥ 2 sources

```python
from collections import defaultdict
with DB() as db:
    by_id = defaultdict(list)
    for r in db.query():
        by_id[r['graph_id']].append(r['source'])
    for gid, srcs in by_id.items():
        if len(srcs) >= 2:
            print(gid, sorted(srcs))
```

### Filter regular K₄-free graphs with α close to the Spencer bound

```python
import math
with DB() as db:
    rows = db.query(is_regular=1, is_k4_free=1, order_by='c_log')
    for r in rows:
        n, d, a = r['n'], r['d_max'], r['alpha']
        spencer = 0.5 * math.sqrt(n * math.log(d)) if d > 1 else float('inf')
        print(f"n={n} d={d} α={a} spencer≈{spencer:.1f}  "
              f"c_log={r['c_log']:.4f}")
```

### Benchmarking a new search against every existing one

Every non-SAT producer in the repo (`brute_force`, `circulant`, `cayley`,
`regularity`, `random`, `mattheus_verstraete`, …) has its output cached
here. When you're building or tuning a new search, **compare against the
cached rows — don't re-run the other searches.** A typical one-liner:

```python
from graph_db import DB

with DB() as db:
    # per-n baseline c_log across every existing source
    baseline = {r['n']: r['c_log']
                for r in db.frontier(by='n', minimize='c_log')}

    # just brute_force (the ground truth where it's feasible)
    bf = {r['n']: r['c_log']
          for r in db.frontier(by='n', minimize='c_log', source='brute_force')}
```

From the shell, the same idea through `db_cli.py`:

```bash
# frontier across all sources, n in [17, 22]
python scripts/db_cli.py query --n 17..22 --top 5 \
    --columns n,c_log,alpha,d_max,source

# frontier filtered to one competitor
python scripts/db_cli.py query --source circulant \
    --columns n,c_log,d_max,alpha
```

SAT/ILP results are **not yet wired into the DB** — they still live under
`reference/pareto/`. Everything else is here; don't re-run a
sweep you can get as a `db.query(...)`.

### Export a frontier to CSV

```python
import csv
with DB() as db, open('frontier.csv', 'w', newline='') as f:
    rows = db.frontier(by='n', minimize='c_log')
    cols = ['n', 'alpha', 'd_max', 'c_log', 'source', 'graph_id']
    w = csv.DictWriter(f, fieldnames=cols, extrasaction='ignore')
    w.writeheader(); w.writerows(rows)
```

---

## Writes

### From a solver / script (preferred)

Producers should write through `GraphStore` directly — no cache work,
no SQLite connection, no property computation on the hot path:

```python
from graph_db import GraphStore, DEFAULT_GRAPHS
import networkx as nx

G = build_candidate()          # any nx.Graph
store = GraphStore(DEFAULT_GRAPHS)
gid, was_new = store.add_graph(
    G, source='my_experiment', filename='my_experiment.json',
    rank=1, solver_time_s=12.3,   # metadata is free-form
)
if was_new:
    print(f"new: {gid}")
```

`add_graph` computes the canonical id + canonical sparse6, skips the
write if `(graph_id, source)` already exists, and appends one record
to `graphs/my_experiment.json`. The cache is populated later, on the
next `db.sync()` (or automatically when someone opens a `DB`).

For bulk writes, use `store.write_batch([...], filename=...)`.

### During interactive analysis

If you're already inside a `DB` session and want the new graph to show
up in `db.query(...)` immediately, `db.add` / `db.add_batch` do the
same append plus invalidate the DB's sparse6 cache. They are
**convenience only** — not the preferred path for bulk producer writes.

```python
with DB() as db:
    gid, was_new = db.add(G, source='my_experiment', rank=1)
```

### If you extend `search/`

Subclass `Search` (see `search/base.py`) — `self.save(G, ...)` and
`self.save_all([...])` wire through `GraphStore` directly.

---

## Sync

Sync reconciles the cache with the store. It's cheap when nothing has
changed (SQLite set-difference) and expensive on fresh rows because it
runs `alpha_exact` (NP-hard), spectral decomposition, etc.

```python
db.sync()                     # add cache rows for any new store records
db.sync(source='circulant')   # restrict to one source
db.sync(recompute=True)       # re-run compute_properties on every row
db.sync(dry_run=True)         # report without writing
```

After changing `compute_properties` (adding a column, fixing a bug), use
`db.sync(recompute=True)` — see `EXTENDING.md` for the full flow.

---

## Clean

`db.clean` (and `python scripts/db_cli.py clean`) does a
**repair-first** pass over `graphs/*.json`:

1. parse each record, re-derive the canonical id and canonical sparse6 from
   the decoded graph, and repair in place if they drift;
2. drop exact `(id, source)` duplicates (global, across all files);
3. prune any now-orphaned cache rows.

```python
python scripts/db_cli.py clean            # dry run — reports only
python scripts/db_cli.py clean --apply    # rewrite JSONs + prune cache
```

Run `clean` after a canonicalization bug fix, or if you suspect
hand-editing of the JSONs has introduced drift. See `DESIGN.md` for the
semantics and when it's safe to run.

---

## CLI cheat sheet

All commands live under `python scripts/db_cli.py`.

```bash
# overview
python scripts/db_cli.py stats

# sync the cache with the store
python scripts/db_cli.py sync
python scripts/db_cli.py sync --source sat_pareto --recompute

# query (scalar or 'A..B' ranges; `..B` and `A..` are open-ended)
python scripts/db_cli.py query --n 17..22 --c-log ..0.75 --top 5
python scripts/db_cli.py query --is-regular 1 --columns graph_id,n,d_max,c_log
python scripts/db_cli.py query --source sat_pareto --json

# add one graph from the shell
python scripts/db_cli.py add --sparse6 ':Is??G_p' --source my_experiment \
    --meta rank=1 --meta note=hand_constructed

# remove
python scripts/db_cli.py rm --source my_experiment -y
python scripts/db_cli.py rm --graph-id 002de366faceec58 --source brute_force -y

# integrity
python scripts/db_cli.py clean             # dry run
python scripts/db_cli.py clean --apply
```

---

## Failure modes worth knowing

| symptom | most likely cause |
|---|---|
| `unknown column 'xxx'` from `query(...)` | column not in `schema.sql`, or typoed. |
| `ValueError: remove(): provide graph_id or source (or both)` | `db.remove()` refuses to wipe the whole table — pass at least one of them. |
| cache row exists but `db.nx(gid)` returns None | the graph was removed from the store but the cache wasn't pruned — run `clean --apply`. |
| `compute_properties` raises on a row | every row in the store is supposed to be a valid K₄-free-ish graph. If one isn't, fix the producer; don't silence the error in `properties.py`. |
| results look stale after editing `properties.py` | `db.sync(recompute=True)`. See `EXTENDING.md`. |
