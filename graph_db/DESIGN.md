# Graph Database — Technical Design

## Goal

Give every solver in the repo (SAT, ILP, circulant, tabu, LLM-search) a
single place to drop the graphs it finds, and give every analysis
script a single place to read them back. "Drop" means writing a tiny
JSON record into `graphs/`; "read" means a typed SQL query over ~35
computed graph properties.

The point of the two-file design (`graphs/` JSON + `cache.db` SQLite) is
to **decouple producing from analyzing** so the same graphs can be
shared, committed, and re-analyzed by multiple machines or pipelines
without coupling producer runtimes to property-computation cost.

## Non-goals

- This is not a general graph DBMS. Queries we care about are all of the
  form `WHERE n <= ? AND c_log < ? AND is_regular = ? ORDER BY c_log`.
  No graph-of-graphs queries, no joins across other entities.
- Not distributed. One folder, one SQLite file, one process at a time.

---

## Two public classes — which to use when

The package exposes two classes and they correspond to two distinct use
cases. Pick the one that matches your job:

| If you want to...                                     | Use                  |
|-------------------------------------------------------|----------------------|
| Add graphs a solver just found                        | **`GraphStore`**     |
| Analyze, query, filter, visualize, hydrate graphs     | **`DB`**             |
| Run a custom SQL query `DB` doesn't expose            | `DB.raw_execute`     |

### `GraphStore` — the producer path

Bare JSON-folder I/O. Producers (SAT sweeps, circulant enumeration,
tabu, LLM loops, manual inserts) just drop graphs into `graphs/` and
stop. **No cache involvement** at write time — property computation
is not a producer concern and should not hold up a long-running search.

```python
from graph_db import GraphStore

store = GraphStore("graphs")
store.add_graph(G, source="my_search", filename="my_search.json",
                solve_time_s=4.2, method="cutting_planes")
```

This is the right path for any producer that just wants to persist new
graphs — e.g. `search_N/base.Search.save` and similar ingest scripts.
All they need is the committed JSON record.

### `DB` — the analysis / visualization path

Combines the store with the property cache. Opening a `DB` auto-syncs
any new store records into the cache (unless `auto_sync=False`), so by
the time you query, every graph has its ~35 typed columns filled.

Use this for the visualizer, leaderboard scripts, comparisons across
sources, hydration of `nx.Graph` objects, rediscovery reports — anything
that reads, ranks, or filters. `DB.add` / `DB.add_batch` are convenience
wrappers that are fine during interactive analysis but are **not** the
preferred path for bulk producer writes (use `GraphStore` directly for
those).

### `DB.raw_execute` — the SQL escape hatch

Rarely needed. Use it only when `DB.query` / `DB.top` / `DB.frontier` /
`DB.stats` don't cover what you want. Typical case: an aggregation or
window function that's easier to express in SQL than in Python.

```python
from graph_db import DB

with DB() as db:
    rows = db.raw_execute(
        "SELECT source, AVG(c_log) FROM cache WHERE n BETWEEN ? AND ? GROUP BY source",
        (20, 30),
    )
```

Rows come back as dicts with JSON columns already deserialised. If you
find yourself reaching for `raw_execute` often, that's a signal the
operation probably belongs as a method on `DB`.

`PropertyCache` (the SQLite-only class that backs this) is an internal
implementation detail — it's intentionally not part of the public
surface. If you think you need it directly (e.g. opening a shipped
`cache.db` without a `graphs/` folder on hand), reach into
`db.cache.raw_execute(...)` via a `DB` built with `auto_sync=False`.

---

## Architecture

```
                       Producers (SAT, circulant, tabu, LLM, manual)
                                        │
                                        │ GraphStore.add_graph(G, source=..., ...)
                                        ▼
                       ┌───────────────────────┐
                       │      graphs/          │
                       │  JSON batch files     │
                       │  (source of truth,    │
                       │   committed)          │
                       └───────────┬───────────┘
                                   │
                                   │ DB.sync() — computes properties
                                   ▼
                       ┌─────────────────────┐
                       │     cache.db        │
                       │   SQLite, typed     │
                       │   one row per       │
                       │  (graph_id, source) │
                       └──────────┬──────────┘
                                  │ DB.query / DB.top / DB.frontier / DB.hydrate
                                  ▼
                    Analyzers (visualizer, leaderboards, comparisons)

       Escape hatch: DB.raw_execute(...)  — custom SQL when needed
```

The two arrows are deliberately separate steps. A producer's job ends
when it has written to `graphs/`; the cache is rebuilt on demand by
whoever wants to analyze. This is why producers don't import `DB`.

### Source of truth — `graphs/*.json`

Each file is a JSON array of records:

```json
[
  {"id": "3f9a1b2c4d5e6f7a",
   "sparse6": ":Kn...",
   "source": "sat_pareto",
   "metadata": {"alpha": 3, "d_max": 8, "solve_time_s": 12.4}}
]
```

**Required fields:** `id`, `sparse6`, `source`. `metadata` is optional
and free-form.

**Why JSON, not SQLite, as the source of truth.** Committed, diffable,
reviewable, tool-agnostic. Contributors can add a file by PR without
touching a binary. Someone who has never seen this repo can still read
the graphs with any JSON parser. The cache is a performance layer on
top, not an authority.

**Batch granularity.** One file per producer run or per conceptual
source. `sat_pareto_ilp.json` collects every Pareto frontier record
from the SAT sweep; `circulants.json` collects the enumeration output.
Splitting per-graph would explode the directory; splitting per-N would
make merging results across methods awkward.

### Derived store — `cache.db`

SQLite with one row per `(graph_id, source)` pair and ~35 typed columns
(degrees, girth, triangles, α, c_log, spectra, MIS vertices, etc.).
Primary key is composite. Indexed on the columns actually filtered on:
`source`, `n`, `c_log`, `alpha`, `d_max`, `is_k4_free`, `is_regular`.

**Why the cache exists.** Three reasons:

1. α(G) is NP-hard. Computing it once and caching it is the only way
   the visualizer opens in under a second.
2. Filtering across hundreds of graphs on `c_log < 0.75 AND n BETWEEN
   20 AND 40 AND is_regular = 1` is a one-line SQL query with indexes,
   versus parsing every JSON file and recomputing properties in Python.
3. It fixes the "every analysis script recomputes the same properties"
   problem. Properties land in one schema and every consumer reads the
   same numbers.

**Why the cache is not the source of truth.** It's opaque, binary, and
expensive to review. A bug in `compute_properties` that writes a wrong
spectral radius shouldn't require a git revert on binary data — we
delete the cache and re-sync from JSON.

**Why SQLite.** One file, no server, typed columns with indexes, ships
with Python's stdlib, diff-able through `sqlite3 .dump`. The schema is
small enough that migrations are a matter of `ALTER TABLE ADD COLUMN`.

---

## The composite key `(graph_id, source)`

This is the one non-obvious design call and it's deliberate.

`graph_id` is the first 16 hex chars of `SHA-256(canonical_sparse6(G))`.
Two isomorphic graphs have the same id regardless of the order in which
their vertices happened to be labelled. Canonicalization uses
`pynauty.canon_graph` (see `utils/pynauty.py`). pynauty is required —
`canonical_id` raises `ImportError` if it is not installed.

A `(graph_id, source)` composite key means the same graph discovered by
two different methods produces two rows. This is intentional:
**rediscovery tracking** is a first-class feature. The interesting
question "did the circulant search and the SAT solver both find P(17)?"
becomes a one-line query:

```sql
SELECT source FROM cache WHERE graph_id = '<P17-hash>'
```

At small N we have exact optima (brute-force up to N=10, SAT up to
N=22). Being able to ask "does any heuristic method rediscover these
optima?" is exactly the signal we want out of this database.

`GraphStore.write_batch` enforces the `(id, source)` uniqueness at
ingest; duplicates within a single source are silently skipped.

---

## Module layout

```
graph_db/
├── __init__.py        Public surface: DB, GraphStore,
│                      compute_properties, encoding helpers
├── DESIGN.md          This file
├── schema.sql         CREATE TABLE + indexes, loaded by cache.py
├── encoding.py        sparse6 ↔ nx, edges_to_nx, graph_to_sparse6
│                      (canonical_id lives in utils/pynauty.py, re-exported here)
├── store.py           GraphStore — JSON folder I/O only (producer path)
├── cache.py           PropertyCache — SQLite only (internal, backs DB)
├── properties.py      compute_properties(G) — the one authoritative scorer
├── db.py              DB — combines store + cache (analysis path)
└── clean.py           Repair, dedup, compact, orphan-prune
```

The CLI lives outside the package at `scripts/db_cli.py` — it's a
client of `DB`, not part of the library itself.

Each file has one responsibility. Intra-package imports flow in one
direction — leaf modules (`encoding`, `cache`, `properties`) import
nothing from the package; higher-level modules compose them:

- `store`     → `encoding`
- `db`        → `store`, `cache`, `encoding`, `properties`, `clean`
- `clean`     → `cache`, `encoding`
- `scripts`   → `db`, `encoding`

No cycles, and the leaves can be unit-tested standalone.

---

## The `DB` class — analysis API

Combines store and cache. This is the class every consumer that reads,
filters, ranks, or visualizes graphs should use. Producers that only
need to add graphs should use `GraphStore` directly and skip `DB`.

### Lifecycle

```python
DB(graphs_dir: str = <repo>/graphs,
   cache_path: str = <repo>/cache.db,
   auto_sync: bool = True)

db.close()
with DB() as db: ...
```

`auto_sync=True` means opening the DB computes properties for any
graphs in the store that don't yet have a cache row. Cheap if the
cache is up-to-date. Set `auto_sync=False` for read-only scripts that
must not touch the cache file.

### Reads

```python
db.get(graph_id, source=None) -> dict | None
    # One row. If source is None, returns first matching row regardless
    # of source (convenient when you just want "a cache row for this graph").

db.get_all(graph_id) -> list[dict]
    # All sources that found this graph. Use this to answer
    # "who rediscovered P(17)?".

db.query(
    where:    dict | None = None,     # {'n': 17, 'is_k4_free': 1}
    ranges:   dict | None = None,     # {'c_log': (0, 0.75), 'n': (20, 40)}
    isin:     dict | None = None,     # {'source': ['sat_pareto', 'circulant']}
    order_by: str | list[str] | None = None,   # 'c_log' asc, '-c_log' desc
    limit:    int | None = None,
    **kwargs,                         # shorthand: db.query(n=17, c_log=(0,1))
) -> list[dict]

db.top(column, k=10, ascending=True, **filters) -> list[dict]
    # SELECT * FROM cache WHERE ... ORDER BY column LIMIT k

db.frontier(by='n', minimize='c_log', **filters) -> list[dict]
    # Best row per distinct `by` value. Used by the visualizer's
    # "only show min c_log per n" toggle.

db.count(**filters) -> int
db.sources() -> list[str]
db.stats() -> dict
    # {n_pairs, n_graphs, n_sources,
    #  n_min, n_max, c_min, c_max,
    #  n_k4_free, n_regular}

db.schema_columns() -> set[str]
    # Every cache column usable in query() / top() / frontier().
    # Useful for UIs that want to expose filters dynamically.
```

**Query shorthand.** `db.query(n=17, is_k4_free=1)` routes scalar kwargs
into `where` and tuple kwargs into `ranges`. This keeps callers that
already use the old positional-ish style working, while giving new
callers the fully explicit form.

**Why `ranges` and `isin` are separate.** Keeping them in their own
dicts means the SQL builder never guesses semantics. `{'c_log':
(0, 1)}` in `where` would be ambiguous — is `(0, 1)` a value or a
range? Separate dicts remove the ambiguity at the API boundary. The
kwargs shorthand collapses them back for ergonomics.

### Graph access

```python
db.sparse6(graph_id) -> str        # The canonical string, from the store.
db.nx(graph_id)      -> nx.Graph   # Decoded on demand.
db.adj(graph_id)     -> np.ndarray # uint8 adjacency matrix.

db.hydrate(records: list[dict]) -> list[dict]
    # Batch: for each row, attach 'sparse6', 'G', 'adj'. One pass over
    # the store. This is what the visualizer calls after query() to
    # avoid the per-record scan.
```

### Writes (convenience only)

```python
db.add(G, source, filename=None, **metadata) -> (graph_id, was_new)
    # Compute id + sparse6, append to graphs/{filename or source.json},
    # and invalidate the DB's sparse6 cache so subsequent reads see it.

db.add_batch(records, filename) -> (added, skipped)
    # Bulk ingest pre-built records. Dedups (id, source) against store.

db.remove(graph_id=None, source=None) -> int
    # Remove matching records from store AND cache. At least one of
    # graph_id/source must be given. Returns number of records removed.
```

`db.add` and `db.add_batch` exist so that a live analysis session can
ingest a just-constructed graph and immediately see it via `db.nx(gid)`
or `db.query(...)`. They are **not** the preferred path for bulk
producer writes (SAT sweeps, circulant enumeration, `search_N.save`,
ad-hoc ingest scripts) — those should write through `GraphStore`
directly to avoid paying for DB construction and auto-sync on every
write.

`db.remove` is the one write that *must* go through `DB` because it
has to remove both the store record and the cache row atomically.

### Sync

```python
db.sync(source=None, recompute=False, dry_run=False, verbose=True) -> dict
    # Compute properties for every (id, source) pair in the store that
    # lacks a cache row.  If recompute=True, force-rewrite existing rows
    # (after a properties.py change).  `source` limits work to one
    # source.  dry_run prints what would be done.

db.recompute(graph_id=None, source=None) -> int
    # Targeted re-sync: recompute properties for one graph, or every
    # graph from one source. Returns number of rows updated.
```

---

## Query examples (visualizer-driven)

The visualizer's current needs:

```python
# "Give me everything, grouped by n, sorted by c_log"
records = db.query()
records = db.hydrate(records)
# → dict of lists in the visualizer, bucketed by n

# "Only show the best c_log per n"
best = db.frontier(by='n', minimize='c_log')

# "Filter to one source"
recs = db.query(source='sat_pareto')

# Cross-graph scatter plot: all points, any two of {n, α, d_max, c_log, m, density}
all_pts = db.query()   # or with a source filter

# Histogram of c_log across all points
values = [r['c_log'] for r in db.query() if r['c_log'] is not None]
```

The visualizer does **not** need SQL. It needs `list[dict]` with the
typed fields present. That's what `query()` returns, with JSON columns
(spectra, degree sequences, MIS vertices) already deserialised back to
Python lists.

---

## Cleanup — `clean.py`

`verify.py` was detect-and-drop. The replacement repairs where it can.

```python
@dataclass
class CleanReport:
    total:            int  # records scanned
    repaired_ids:     int  # stored id was wrong, rewrote to canonical
    repaired_sparse6: int  # sparse6 wasn't canonical, re-canonicalized
    duplicates:       int  # (id, source) pairs dropped as duplicates
    unparseable:      list[dict]   # records that had to be dropped
    files_rewritten:  int
    files_removed:    int  # empty files
    orphaned_cache:   int  # cache rows whose (id, source) left the store
```

### What it does

1. **Load everything.** Read every record from every `graphs/*.json`
   into memory.
2. **Repair IDs and sparse6.** For each record:
   - Parse sparse6. If it fails, stage for removal (report only —
     never silently lose graphs without logging).
   - Recompute canonical sparse6 and canonical id.
   - If canonical sparse6 differs from stored, rewrite both fields
     (`repaired_sparse6 += 1`, `repaired_ids += 1` if id also moved).
3. **Global dedup.** Build a map `(id, source) → first_record`. Any
   further record with the same key is dropped (`duplicates += 1`).
   Dedup is global across all files — current `verify.py` only
   dedups within one file.
4. **Rewrite files.** Each input file is rewritten with its surviving
   records. If zero survive, the file is removed
   (`files_removed += 1`).
5. **Prune cache.** Any `(graph_id, source)` row in `cache.db` that no
   longer maps to a record in `graphs/` is deleted.

### Safety

- `dry_run=True` does all the work in memory and returns the report
  without writing.
- Unparseable records are never silently dropped without being listed
  in the report — the human reviewing the output decides.
- Backups are not written. `clean` defaults to dry-run; the caller must
  pass `--apply` to actually rewrite. Running under a clean git working
  tree is the recommended safety net.

---

## CLI — `scripts/db_cli.py`

Run as `python scripts/db_cli.py <subcommand>`. All subcommands are
thin argparse wrappers over `DB` methods; no business logic lives in
the CLI.

```
sync    [--source NAME] [--recompute] [--dry-run]
        Ingest any new graphs and/or force-recompute existing rows.

clean   [--apply]
        Repair canonical forms, dedup globally, prune orphan cache
        rows. Dry run by default — pass --apply to rewrite.

add     --sparse6 S | --g6 S | --edges JSON -n N
        --source TAG [--file NAME] [--meta K=V ...] [--no-sync]
        Append a single graph to the store.

query   [--source ...] [--n A..B] [--c-log ..T] [--is-regular 0|1]
        [--is-k4-free 0|1] [--alpha A..B] [--d-max A..B]
        [--top K] [--order-by COL] [--limit N]
        [--columns graph_id,n,c_log,source] [--json]
        Print matching cache rows (TSV by default, JSON with --json).

rm      [--graph-id ID] [--source TAG] [-y]
        Remove matching records from store AND cache. At least one of
        --graph-id / --source required.

stats   Print summary: total graphs, per-source counts, c_log
        range, n range, count of k4-free / regular.
```

Sample session:

```bash
python scripts/db_cli.py sync
python scripts/db_cli.py stats
python scripts/db_cli.py query --n 17..22 --c-log ..0.75 --top 10 --order-by c_log
python scripts/db_cli.py clean --dry-run
python scripts/db_cli.py clean
```

---

## Producer contract

A producer (SAT solver, circulant search, LLM loop, manual CLI add)
writes graphs it finds by calling `GraphStore.add_graph(G,
source=<own_tag>, filename=<tag>.json, **metadata)`, or by dropping a
pre-built record into `graphs/<tag>.json` directly. It does not import
`DB`, does not touch the cache, does not compute properties, does not
canonicalize ids beyond what `add_graph` does internally. All of that
happens later, on `DB.sync()`.

This decoupling is deliberate. Long-running searches shouldn't pay for
property computation (α is NP-hard), shouldn't open SQLite connections,
and shouldn't block on anything that isn't "append a record to a JSON
file." When an analyst wants to compare results across sources, they
open a `DB`, which syncs once and serves typed queries from there on.

**Metadata convention.** The `metadata` dict on each record is for
*solver-specific, free-form* fields: `solve_time_s`, `method`,
`iterations`, `connection_set`, `rank`, `seed`, lineage, etc. Do not
put fields that `compute_properties` already produces (`alpha`,
`d_max`, `c_log`, `n`, `m`, `degree_sequence`, …) into metadata — the
cache is the single source of truth for those, and duplicating them in
metadata invites drift (producer-rounded `c_log` vs cache-computed
`c_log` on the same graph).

Producers set their source tag to a stable identifier. Suggested
conventions (enforced nowhere):

| Tag              | Producer                                   |
|------------------|--------------------------------------------|
| `sat_pareto`     | CP-SAT Pareto scan                         |
| `regular_sat`    | Near-regular CP-SAT                        |
| `circulant`      | Circulant enumeration                      |
| `brute_force`    | Small-N exhaustive                         |
| `claude_search`  | LLM-in-the-loop                            |
| `manual`         | Hand-entered                               |
| `r45_mckay`      | External: McKay's R(4,5) database          |

Same graph discovered by two tags → two rows. That's the point.

---

## Failure modes and what the design guarantees

| Failure                                   | Outcome                                             |
|-------------------------------------------|-----------------------------------------------------|
| `graphs/*.json` has a malformed record    | `sync` skips it; `clean` reports and (optionally) removes it |
| Wrong id in a record (mismatch with sparse6) | `clean` repairs the id in place |
| Non-canonical sparse6 (legal but suboptimal) | `clean` rewrites to canonical and repairs id |
| Same `(id, source)` appears twice         | `clean` keeps the first, drops duplicates |
| Same graph from two sources               | **Kept** — two cache rows, by design |
| `compute_properties` gets a new column    | `ALTER TABLE ADD COLUMN`, then `db.sync(recompute=True)` |
| Cache corruption                          | Delete `cache.db`, re-run `sync` |
| pynauty missing                           | `canonical_id` raises `ImportError` — install pynauty (`pip install pynauty` or activate the 4cycle env) |

What the design does **not** guarantee:

- **Concurrent writers.** Two processes calling `db.add` at the same
  time can race on the JSON rewrite. This is out of scope — assume one
  writer at a time.
- **Cross-machine cache consistency.** `cache.db` is gitignored; every
  machine builds its own from the committed `graphs/` folder. If you
  want a shared cache, distribute it out-of-band.
