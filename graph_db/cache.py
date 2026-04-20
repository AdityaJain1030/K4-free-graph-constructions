"""
graph_db/cache.py
=================
SQLite-backed property cache. One row per (graph_id, source) pair with
every computable property as a typed column. Rebuildable from the
graph store at any time — see DESIGN.md.
"""

import json
import os
import sqlite3


_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

# Bootstrap DDL run before schema.sql so new nullable columns can be
# ALTER-added by _migrate_add_missing_columns ahead of the CREATE
# INDEX statements in the full schema.
_BASE_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS cache (
    graph_id    TEXT NOT NULL,
    source      TEXT NOT NULL,
    PRIMARY KEY (graph_id, source)
);
"""

# Order must match the column order of the INSERT below.
_INSERT_COLUMNS = (
    "graph_id",  "source",
    "n", "m", "density",
    "d_min", "d_max", "d_avg", "d_var",
    "degree_sequence", "is_regular", "regularity_d",
    "is_connected", "n_components", "diameter", "radius",
    "edge_connectivity", "vertex_connectivity",
    "girth", "n_triangles", "avg_clustering", "assortativity",
    "clique_num", "greedy_chromatic_bound", "is_k4_free",
    "eigenvalues_adj", "spectral_radius", "spectral_gap", "n_distinct_eigenvalues",
    "eigenvalues_lap", "algebraic_connectivity",
    "alpha", "c_log", "beta", "turan_density",
    "codegree_avg", "codegree_max",
    "mis_vertices", "triangle_edges", "triangle_vertices", "high_degree_vertices",
    "metadata",
)

_JSON_COLUMNS = (
    "degree_sequence", "eigenvalues_adj", "eigenvalues_lap",
    "mis_vertices", "triangle_edges", "triangle_vertices",
    "high_degree_vertices", "metadata",
)


def _load_schema() -> str:
    with open(_SCHEMA_PATH) as f:
        return f.read()


class PropertyCache:
    """SQLite property cache. One row per (graph_id, source) pair."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate_legacy()
        # Ensure a base table exists (no-op if present).
        self._conn.execute(_BASE_TABLE_DDL)
        # Add any missing nullable columns before running the full schema
        # script — otherwise CREATE INDEX on a new column would fail on
        # older databases that never had the column.
        self._migrate_add_missing_columns()
        self._conn.executescript(_load_schema())
        self._conn.commit()

    # ── lifecycle ─────────────────────────────────────────────────────────────

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _migrate_legacy(self):
        """If an older single-PK `cache` table exists, drop it so the new composite-PK schema applies."""
        row = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='cache'"
        ).fetchone()
        if row and "PRIMARY KEY (graph_id, source)" not in row[0]:
            self._conn.execute("DROP TABLE cache")
            self._conn.commit()

    # Nullable columns that may be missing on older cache.db files. Any
    # time a new property is added to schema.sql with a nullable type,
    # list it here with its SQL type so existing caches ALTER-in the
    # column silently on next open. Values are NULL until a recompute
    # fills them in.
    _AUTO_ADD_COLUMNS = (
        ("codegree_avg", "REAL"),
        ("codegree_max", "INTEGER"),
    )

    def _migrate_add_missing_columns(self):
        cols = {r[1] for r in self._conn.execute("PRAGMA table_info(cache)")}
        for name, sql_type in self._AUTO_ADD_COLUMNS:
            if name not in cols:
                self._conn.execute(f"ALTER TABLE cache ADD COLUMN {name} {sql_type}")

    # ── reads ─────────────────────────────────────────────────────────────────

    def cached_pairs(self) -> set[tuple[str, str]]:
        return {(r[0], r[1]) for r in self._conn.execute(
            "SELECT graph_id, source FROM cache"
        )}

    def cached_ids(self) -> set[str]:
        return {r[0] for r in self._conn.execute(
            "SELECT DISTINCT graph_id FROM cache"
        )}

    def all_sources(self) -> list[str]:
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT source FROM cache ORDER BY source"
        )]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

    def get(self, graph_id: str, source: str | None = None) -> dict | None:
        if source is not None:
            row = self._conn.execute(
                "SELECT * FROM cache WHERE graph_id = ? AND source = ?",
                (graph_id, source),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT * FROM cache WHERE graph_id = ?", (graph_id,)
            ).fetchone()
        return self._deserialise(dict(row)) if row else None

    def get_all(self, graph_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM cache WHERE graph_id = ?", (graph_id,)
        ).fetchall()
        return [self._deserialise(dict(r)) for r in rows]

    def raw_execute(self, sql: str, params: tuple = ()) -> list[dict]:
        """Run arbitrary SELECT against the cache. Rows are returned deserialised."""
        rows = self._conn.execute(sql, params).fetchall()
        return [self._deserialise(dict(r)) for r in rows]

    # ── writes ────────────────────────────────────────────────────────────────

    def insert(self, graph_id: str, source: str, props: dict, metadata: dict):
        """Insert-or-replace one row for (graph_id, source)."""
        j = json.dumps
        values = (
            graph_id, source,
            props["n"], props["m"], props["density"],
            props["d_min"], props["d_max"], props["d_avg"], props["d_var"],
            j(props["degree_sequence"]),
            int(props["is_regular"]), props["regularity_d"],
            int(props["is_connected"]), props["n_components"],
            props["diameter"], props["radius"],
            props["edge_connectivity"], props["vertex_connectivity"],
            props["girth"], props["n_triangles"],
            props["avg_clustering"], props["assortativity"],
            props["clique_num"], props["greedy_chromatic_bound"],
            int(props["is_k4_free"]),
            j(props["eigenvalues_adj"]), props["spectral_radius"],
            props["spectral_gap"], props["n_distinct_eigenvalues"],
            j(props["eigenvalues_lap"]), props["algebraic_connectivity"],
            props["alpha"], props["c_log"], props["beta"],
            props["turan_density"],
            props["codegree_avg"], props["codegree_max"],
            j(props["mis_vertices"]), j(props["triangle_edges"]),
            j(props["triangle_vertices"]), j(props["high_degree_vertices"]),
            j(metadata),
        )
        placeholders = ",".join("?" for _ in _INSERT_COLUMNS)
        self._conn.execute(
            f"INSERT OR REPLACE INTO cache ({','.join(_INSERT_COLUMNS)}) "
            f"VALUES ({placeholders})",
            values,
        )
        self._conn.commit()

    def delete(self, graph_id: str | None = None, source: str | None = None) -> int:
        """Delete rows matching (graph_id, source). At least one must be given."""
        if graph_id is None and source is None:
            raise ValueError("delete(): provide graph_id or source (or both)")
        where, params = [], []
        if graph_id is not None:
            where.append("graph_id = ?")
            params.append(graph_id)
        if source is not None:
            where.append("source = ?")
            params.append(source)
        cur = self._conn.execute(
            f"DELETE FROM cache WHERE {' AND '.join(where)}", params
        )
        self._conn.commit()
        return cur.rowcount

    def prune_orphans(self, valid_pairs: set[tuple[str, str]]) -> int:
        """Delete cache rows whose (graph_id, source) is not in valid_pairs."""
        cached = self.cached_pairs()
        orphans = cached - valid_pairs
        for gid, src in orphans:
            self._conn.execute(
                "DELETE FROM cache WHERE graph_id = ? AND source = ?", (gid, src)
            )
        if orphans:
            self._conn.commit()
        return len(orphans)

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _deserialise(row: dict) -> dict:
        for col in _JSON_COLUMNS:
            v = row.get(col)
            if isinstance(v, str):
                row[col] = json.loads(v)
        return row

    # expose for the DB class's query builder
    @staticmethod
    def schema_columns() -> set[str]:
        """Return the set of whitelisted column names that can appear in queries."""
        return {
            "graph_id", "source", "n", "m", "density",
            "d_min", "d_max", "d_avg", "d_var",
            "degree_sequence", "is_regular", "regularity_d",
            "is_connected", "n_components", "diameter", "radius",
            "edge_connectivity", "vertex_connectivity",
            "girth", "n_triangles", "avg_clustering", "assortativity",
            "clique_num", "greedy_chromatic_bound", "is_k4_free",
            "spectral_radius", "spectral_gap", "n_distinct_eigenvalues",
            "algebraic_connectivity",
            "alpha", "c_log", "beta", "turan_density",
            "codegree_avg", "codegree_max",
        }
