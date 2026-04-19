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

The full whitelist lives in `PropertyCache.schema_columns()`.

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

### From a solver / script

```python
from graph_db import DB
import networkx as nx

G = build_candidate()          # any nx.Graph
with DB() as db:
    gid, was_new = db.add(G, source='my_experiment', filename='my_experiment.json',
                          rank=1, solver_time_s=12.3)    # metadata is free-form
    if was_new:
        print(f"new: {gid}")
```

`db.add` computes the canonical id + canonical sparse6 for you, skips the
write if `(graph_id, source)` already exists, and triggers a cache update
for the new pair on the next `sync` (or auto-sync).

For bulk writes from a tight loop, use `db.add_batch([...], filename=...)`.

### If you extend `search_N/`

Subclass `Search` (see `search_N/base.py`) — it already wires `self.save(G, ...)`
and `self.save_all([...])` through the DB.

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

`db.clean` (and `python -m graph_db.scripts clean`) does a
**repair-first** pass over `graphs/*.json`:

1. parse each record, re-derive the canonical id and canonical sparse6 from
   the decoded graph, and repair in place if they drift;
2. drop exact `(id, source)` duplicates (global, across all files);
3. prune any now-orphaned cache rows.

```python
python -m graph_db.scripts clean            # dry run — reports only
python -m graph_db.scripts clean --apply    # rewrite JSONs + prune cache
```

Run `clean` after a canonicalization bug fix, or if you suspect
hand-editing of the JSONs has introduced drift. See `DESIGN.md` for the
semantics and when it's safe to run.

---

## CLI cheat sheet

All commands live under `python -m graph_db.scripts`.

```bash
# overview
python -m graph_db.scripts stats

# sync the cache with the store
python -m graph_db.scripts sync
python -m graph_db.scripts sync --source sat_pareto --recompute

# query (scalar or 'A..B' ranges; `..B` and `A..` are open-ended)
python -m graph_db.scripts query --n 17..22 --c-log ..0.75 --top 5
python -m graph_db.scripts query --is-regular 1 --columns graph_id,n,d_max,c_log
python -m graph_db.scripts query --source sat_pareto --json

# add one graph from the shell
python -m graph_db.scripts add --sparse6 ':Is??G_p' --source my_experiment \
    --meta rank=1 --meta note=hand_constructed

# remove
python -m graph_db.scripts rm --source my_experiment -y
python -m graph_db.scripts rm --graph-id 002de366faceec58 --source brute_force -y

# integrity
python -m graph_db.scripts clean             # dry run
python -m graph_db.scripts clean --apply
```

---

## Failure modes worth knowing

| symptom | most likely cause |
|---|---|
| `unknown column 'xxx'` from `query(...)` | column not in `schema.sql`, or typoed. |
| `ValueError: delete(): provide graph_id or source` | `db.remove()` refuses to wipe the whole table — pass at least one of them. |
| cache row exists but `db.nx(gid)` returns None | the graph was removed from the store but the cache wasn't pruned — run `clean --apply`. |
| `compute_properties` raises on a row | every row in the store is supposed to be a valid K₄-free-ish graph. If one isn't, fix the producer; don't silence the error in `properties.py`. |
| results look stale after editing `properties.py` | `db.sync(recompute=True)`. See `EXTENDING.md`. |
