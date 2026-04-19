# Adding a cached property to graph_db

The cache (`cache.db`) has one row per `(graph_id, source)` pair with
~35 typed columns. Adding a new column — say a property `my_invariant` —
touches four files and one one-shot command. This doc is the checklist.

Read `DESIGN.md` for the rationale; read `USAGE.md` for how to query what
already exists.

---

## TL;DR — the five touch points

1. **`schema.sql`** — declare the column (+ optional index).
2. **`cache.py`** — add the name to `_INSERT_COLUMNS` (and `_JSON_COLUMNS`
   if it's a list/dict), and to `schema_columns()` if you want it
   queryable.
3. **`properties.py`** — compute the value in `compute_properties(G)` and
   write it to `p["my_invariant"]`.
4. **Your sync** — `python scripts/db_cli.py sync --recompute` to
   backfill every existing row.
5. **Verify** — `db.query(my_invariant=...)` works; `db.stats()` is still
   sane.

---

## 1. Declare the column in `schema.sql`

Types that map cleanly to SQLite:

| Python type       | SQLite type | nullable when... |
|-------------------|-------------|------------------|
| `int` / `bool`    | `INTEGER`   | the property can be undefined (e.g., diameter of disconnected graph) |
| `float`           | `REAL`      | d_max ≤ 1, etc. |
| `str` / `list` / `dict` | `TEXT` (stored as JSON) | always `TEXT NOT NULL` — use `'[]'` or `'{}'` as default |

Scalar example:

```sql
CREATE TABLE IF NOT EXISTS cache (
    ...
    my_invariant            REAL,
    ...
);
```

If you plan to filter by this column a lot, add an index:

```sql
CREATE INDEX IF NOT EXISTS idx_my_invariant ON cache(my_invariant);
```

If it's a list-valued property (vertex sets, edge lists, etc.):

```sql
    my_vertex_set           TEXT    NOT NULL,   -- JSON-encoded list
```

The `_migrate_legacy` hook in `cache.py` only handles legacy PK changes.
For a plain column-add, SQLite will pick up the new schema on next open
because the schema uses `CREATE TABLE IF NOT EXISTS`. **But existing DB
files won't gain the column automatically** — you have two options:

- Throw away `cache.db` and let sync rebuild (fastest, safest for dev).
- Run `ALTER TABLE cache ADD COLUMN my_invariant REAL;` manually, then
  `db.sync(recompute=True)`.

For production caches with expensive properties (α is NP-hard), prefer
`ALTER TABLE` + targeted recompute.

---

## 2. Wire the column into `cache.py`

Two or three edits:

**`_INSERT_COLUMNS`** — append the new name **in the same position** it
appears in `schema.sql`'s column order. The tuple drives the `INSERT OR
REPLACE` statement, so position matters.

```python
_INSERT_COLUMNS = (
    "graph_id", "source",
    ...
    "my_invariant",
    "metadata",
)
```

**`_JSON_COLUMNS`** — only if the value is a list or dict. This drives
JSON encode on write and decode on read.

```python
_JSON_COLUMNS = (
    "degree_sequence", "eigenvalues_adj", ...,
    "my_vertex_set",
)
```

**`schema_columns()`** — the whitelist the `DB.query()` builder validates
against. Add your column here so callers can filter/order on it:

```python
@staticmethod
def schema_columns() -> set[str]:
    return {
        ...,
        "my_invariant",
    }
```

Leave it out of `schema_columns()` if the column is intentionally
read-only (e.g., a pre-computed blob that doesn't make sense to filter
by).

**The `insert()` method** also needs the value read out of `props`:

```python
values = (
    graph_id, source,
    ...
    props["my_invariant"],
    j(metadata),
)
```

(Or `j(props["my_vertex_set"])` for JSON-encoded list columns.)

---

## 3. Compute the value in `properties.py`

`compute_properties(G: nx.Graph) -> dict` is the single place every
cached property is computed. Add one block:

```python
# --- My invariant ---
p["my_invariant"] = compute_my_invariant(G)
```

Where `compute_my_invariant` lives is up to you:

- If it's a general graph invariant → add it to `utils/graph_props.py`
  and import it at the top of `properties.py`. That keeps it reusable
  for SAT/ILP/tabu callers who don't touch the DB.
- If it's derived from other cached columns → compute it inline in
  `compute_properties`.

Return types should match what the schema expects: Python `int`/`float`/
`bool`/`None`/`list`/`dict`. The `cache.insert()` layer JSON-encodes
list/dict values for `_JSON_COLUMNS` — don't pre-encode yourself.

**Edge cases to handle in the compute function**, not downstream:

- `n == 0` or `n == 1` — guard early and return a sensible constant.
- Disconnected graphs — `None` is fine for diameter-like properties.
- Pathologically dense or sparse graphs — document the behaviour.

If your property is expensive (matches the cost profile of `alpha_exact`,
spectral decomposition, SAT solving), put it *after* cheap invariants in
`compute_properties` so an early exception doesn't waste the computation.

---

## 4. Back-fill existing rows

Once the code changes are in:

```bash
# Option A — dev, small dataset, don't care about recomputation cost
rm cache.db
python scripts/db_cli.py sync

# Option B — incremental, preserves the existing cache
# first apply the ALTER TABLE if needed, then:
python scripts/db_cli.py sync --recompute
```

`sync --recompute` re-runs `compute_properties` on every `(graph_id,
source)` pair and `INSERT OR REPLACE`s the row. Progress is streamed
to stdout with `[i/N] id=... source=... n=... c_log=...`.

For a partial backfill (one source only):

```bash
python scripts/db_cli.py sync --recompute --source my_experiment
```

---

## 5. Verify

```python
from graph_db import DB

with DB() as db:
    # column is queryable?
    db.query(my_invariant=(0, 1), limit=5)

    # value looks right on a known graph?
    r = db.query(n=10, source='brute_force', limit=1)[0]
    print(r['my_invariant'])

    # stats haven't regressed?
    print(db.stats())
```

If the column is a list/set, also spot-check that it decoded correctly:

```python
print(type(r['my_vertex_set']))   # list, not str
```

---

## Removing a column

Essentially the reverse, minus SQLite's annoying lack of `DROP COLUMN`
support on old versions:

1. remove from `schema.sql`, `_INSERT_COLUMNS`, `_JSON_COLUMNS`,
   `schema_columns()`, and `compute_properties`;
2. blow away `cache.db` (cheap) and `sync` — usually easier than issuing
   an `ALTER TABLE DROP COLUMN` in SQLite.

Readers querying a removed column will fail with
`unknown column 'xxx'` — intentional; that's what the whitelist is for.

---

## Tips

- **Don't add columns you won't query.** Metadata bags on the JSON
  records (`rec["metadata"]`) are cheaper if you only need the value
  alongside the graph, not as a filter.
- **Don't silently swallow errors in compute_properties.** If a property
  can genuinely be undefined, return `None` and make the column nullable.
  If computation *should* succeed but didn't, let it raise — a broken
  property is better caught at sync time than discovered weeks later.
- **List-valued properties need determinism**. Sort the list before
  storing so two callers with the same graph get byte-identical rows.
- **Think about isomorphism invariance**. Two records for the same graph
  (different sources) currently store the same sparse6, so they will also
  store the same property values. If your invariant depends on vertex
  labels, you will silently break that invariant. Write graph-invariant
  values only.
