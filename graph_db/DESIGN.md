# Graph Database Design

Two separate stores:

- **`graphs/`** — a folder of JSON files, one per graph. The source of truth for what graphs exist. Human-readable, git-friendly, no dependencies.
- **`cache.db`** — a SQLite database with one row per graph and every computable property as a typed column. Rebuilt from `graphs/` at any time. Never committed to git.

---

## Store 1: `graphs/` folder

Each file in `graphs/` contains a JSON array of graph records. One file per batch — name it whatever makes sense for the source (e.g. `sat_pareto_n17.json`, `circulants_n8_50.json`). A single file can hold one graph or ten thousand.

```json
[
  {
    "id":      "3f9a1b2c4d5e6f7a",
    "sparse6": ":Kn...",
    "source":  "sat_pareto"
  },
  {
    "id":      "9a4f2d1e8b3c7f05",
    "sparse6": ":Lo...",
    "source":  "sat_pareto",
    "metadata": {
      "alpha":          3,
      "d_max":          8,
      "solve_time_s":   12.4,
      "sat_iterations": 7,
      "n":              17
    }
  }
]
```

**`id`, `sparse6`, and `source` are required per record. Everything else is optional.**

The optional `metadata` block holds free-form source-specific fields — SAT solve time, circulant jump set, SAT iteration count, whatever. No schema, no validation. It is stored verbatim in the `metadata` column of `cache.db` and is never used to skip computation.

### Source

`source` is a free-form string — any value is valid. The UI reads all distinct source values from `cache.db` and exposes them as a filter. Suggested conventions for consistency:

| Example value | Meaning |
|---|---|
| `sat_pareto` | ILP Pareto frontier sweep |
| `regular_sat` | Near-regular SAT solver |
| `circulant` | Circulant graph enumeration |
| `claude_search` | LLM-guided algebraic search |
| `manual` | Hand-constructed or from literature |
| `r45_mckay` | McKay's R(4,5) database |

These are just conventions. The system imposes no restriction on what strings appear.

### Deduplication

`id` = `SHA-256[:16]` of the **canonical sparse6**. Two isomorphic graphs produce the same id — the second record is silently skipped on cache-fill.

Canonical sparse6 is produced by:
1. **pynauty** (Linux / Mac with nauty binary) — true canonical labelling
2. **WL hash fallback** — Weisfeiler-Lehman graph hash (networkx, 6 iterations) — reliable for K₄-free graphs up to N~100 but not a proof of non-isomorphism on collision

### Why multiple graphs per file

- Appending a batch of results = write one file, no need to touch existing files
- A SAT run over N=20..35 produces one file; a circulant enumeration produces another; they coexist cleanly
- Files stay human-readable and git-diffable at reasonable batch sizes (hundreds to low thousands of graphs per file)

---

## Store 2: `cache.db` (SQLite)

One row per graph. Every row is complete — all columns populated — before the UI opens. Filtered queries (e.g. "all K₄-free graphs with c_log < 0.75 and n in [20,40] and is_regular = 1") are plain SQL WHERE clauses with indexes.

```sql
CREATE TABLE cache (
    graph_id  TEXT PRIMARY KEY,   -- matches id in graphs/*.json
    source    TEXT    NOT NULL,   -- copied from the graph record; indexed for UI filter

    -- Basic
    n                       INTEGER NOT NULL,
    m                       INTEGER NOT NULL,
    density                 REAL    NOT NULL,

    -- Degree
    d_min                   INTEGER NOT NULL,
    d_max                   INTEGER NOT NULL,
    d_avg                   REAL    NOT NULL,
    d_var                   REAL    NOT NULL,
    degree_sequence         TEXT    NOT NULL,   -- JSON [int, ...]  sorted ascending
    is_regular              INTEGER NOT NULL,   -- 0 or 1
    regularity_d            INTEGER,            -- NULL if not regular

    -- Connectivity
    is_connected            INTEGER NOT NULL,   -- 0 or 1
    n_components            INTEGER NOT NULL,
    diameter                INTEGER,            -- NULL if disconnected
    radius                  INTEGER,            -- NULL if disconnected
    edge_connectivity       INTEGER,            -- NULL if disconnected
    vertex_connectivity     INTEGER,            -- NULL if disconnected

    -- Cycles / substructure
    girth                   INTEGER,            -- NULL if acyclic
    n_triangles             INTEGER NOT NULL,
    avg_clustering          REAL    NOT NULL,
    assortativity           REAL,               -- NULL for regular graphs (undefined)

    -- Clique / chromatic
    clique_num              INTEGER NOT NULL,   -- omega(G)
    greedy_chromatic_bound  INTEGER NOT NULL,   -- upper bound on chi(G)
    is_k4_free              INTEGER NOT NULL,   -- 0 or 1

    -- Spectral (adjacency)
    eigenvalues_adj         TEXT    NOT NULL,   -- JSON [float, ...]  descending
    spectral_radius         REAL    NOT NULL,
    spectral_gap            REAL,               -- NULL if n = 1
    n_distinct_eigenvalues  INTEGER NOT NULL,

    -- Spectral (Laplacian)
    eigenvalues_lap         TEXT    NOT NULL,   -- JSON [float, ...]  ascending
    algebraic_connectivity  REAL,               -- Fiedler value, NULL if disconnected

    -- Extremal / conjecture
    alpha                   INTEGER NOT NULL,
    c_log                   REAL,               -- alpha*d_max / (n*ln(d_max)), NULL if d_max <= 1
    beta                    REAL,               -- d_avg = (n/alpha)*ln(n/alpha)^beta, NULL if undefined
    turan_density           REAL    NOT NULL,   -- m / |E(T(n,3))|

    -- Highlight sets (for visualizer)
    mis_vertices            TEXT    NOT NULL,   -- JSON [int, ...]
    triangle_edges          TEXT    NOT NULL,   -- JSON [[i,j], ...]
    triangle_vertices       TEXT    NOT NULL,   -- JSON [int, ...]
    high_degree_vertices    TEXT    NOT NULL,   -- JSON [int, ...]

    -- Free-form extras (passed through from graphs/{id}.json metadata block)
    metadata                TEXT    NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_source   ON cache(source);
CREATE INDEX idx_n        ON cache(n);
CREATE INDEX idx_c_log    ON cache(c_log);
CREATE INDEX idx_alpha    ON cache(alpha);
CREATE INDEX idx_d_max    ON cache(d_max);
CREATE INDEX idx_is_k4    ON cache(is_k4_free);
CREATE INDEX idx_regular  ON cache(is_regular);
```

The `metadata` column mirrors the `metadata` block from the graph JSON verbatim. It is not indexed or queried by the core system — it is there so that source-specific fields (solve time, SAT iteration count, circulant jump set, etc.) are available in the cache row without polluting the typed schema.

### Adding new typed fields

```sql
ALTER TABLE cache ADD COLUMN new_field TYPE DEFAULT default_value;
```

Old rows get the default. On next startup, `compute_properties()` is updated to populate `new_field` for any newly ingested graphs. To backfill existing rows, run a one-off script:

```python
for gid in db.all_ids():
    val = compute_new_field(db.get_nx(gid))
    db.execute("UPDATE cache SET new_field = ? WHERE graph_id = ?", (val, gid))
```

No rows are deleted. No data is lost.

---

## Load sequence

```
startup
  │
  ├── scan graphs/*.json  →  parse every array, collect all records
  │                          keyed by id  (duplicates: last write wins,
  │                          or skip — dedup by id is idempotent)
  │
  ├── query cache.db      →  set of cached ids
  ├── missing = known_ids - cached_ids
  │
  └── for each id in missing:
        rec   = records[id]
        G     = sparse6_to_nx(rec["sparse6"])
        props = compute_properties(G)
        INSERT INTO cache (graph_id, source, ..., metadata) VALUES (...)
        [show progress bar if len(missing) > 10]
  │
  └── UI ready — all filters guaranteed to work
        source filter: SELECT DISTINCT source FROM cache  (shown as checkboxes)
```

### Computation cost per graph

| Field group | Typical time |
|---|---|
| Basic stats, degrees, density | < 1 ms |
| Girth, triangles, clustering | 1–10 ms |
| Spectral (N×N eigendecomposition) | 1–50 ms |
| Connectivity, edge/vertex conn | 1–20 ms |
| Alpha / MIS — **exact** | 1 ms – minutes (N and structure dependent) |

Alpha is the bottleneck for large N. Always pass `alpha` in `hint` from the source when available.

---

## File layout

```
graph_db/
  DESIGN.md        ← this file
  store.py         ← GraphStore: reads graphs/ folder, writes cache.db
  properties.py    ← compute_properties(G, hint) → full cache row dict
  __init__.py

graphs/                          ← committed to git
  sat_pareto_n12_n35.json        ← array of graph records from SAT run
  regular_sat_n9_n35.json        ← array from near-regular SAT
  circulants_n8_n50.json         ← array from circulant enumeration
  claude_search.json             ← array from LLM search
  ...                            ← one file per batch / source run

cache.db                         ← gitignored, rebuilt on demand
```
