"""
graph_db/store.py
=================
Graph store (JSON folder) + property cache (SQLite).

Graph store
-----------
graphs/*.json  — each file is a JSON array of records:
    [{"id": str, "sparse6": str, "source": str, "metadata": {...}}, ...]

Deduplication key is (id, source).  The same graph may appear multiple times
if discovered by different methods — that is intentional.  Two records with
the same id AND same source are considered duplicates.

Cache
-----
cache.db  — SQLite, one row per (graph_id, source) pair with every computable
            property.  Rebuilt from the graph store at any time.
"""

import glob
import hashlib
import json
import os
import sqlite3
import warnings
from typing import Any

import networkx as nx
warnings.filterwarnings("ignore", category=UserWarning, module="networkx")

from utils.pynauty import has_pynauty as _has_pynauty


def _to_int_graph(G) -> nx.Graph:
    if not isinstance(G, nx.Graph):
        import numpy as np
        G = nx.from_numpy_array(np.array(G, dtype=np.uint8))
    return nx.convert_node_labels_to_integers(G)


def _canonical_sparse6_pynauty(G: nx.Graph) -> str:
    import pynauty
    n = G.number_of_nodes()
    adj = {v: list(G.neighbors(v)) for v in range(n)}
    g = pynauty.Graph(n, adjacency_dict=adj)
    cert = pynauty.certificate(g)
    H = nx.Graph()
    H.add_nodes_from(range(n))
    bit = 0
    for i in range(n):
        for j in range(i + 1, n):
            byte_pos, bit_pos = bit // 8, 7 - (bit % 8)
            if byte_pos < len(cert) and (cert[byte_pos] >> bit_pos) & 1:
                H.add_edge(i, j)
            bit += 1
    return nx.to_sparse6_bytes(H, header=False).decode("ascii").strip()


def canonical_id(G) -> tuple[str, str]:
    """
    Return (graph_id, canonical_sparse6).
    graph_id = SHA-256[:16] of canonical_sparse6.
    Falls back to WL hash if pynauty is unavailable.
    """
    G = _to_int_graph(G)
    if _has_pynauty():
        try:
            cs6 = _canonical_sparse6_pynauty(G)
            return hashlib.sha256(cs6.encode()).hexdigest()[:16], cs6
        except Exception:
            pass
    wl = nx.weisfeiler_lehman_graph_hash(G, iterations=6)
    gid = hashlib.sha256(wl.encode()).hexdigest()[:16]
    return gid, wl


def graph_to_sparse6(G) -> str:
    G = _to_int_graph(G)
    return nx.to_sparse6_bytes(G, header=False).decode("ascii").strip()


def sparse6_to_nx(s6: str) -> nx.Graph:
    return nx.from_sparse6_bytes(s6.encode("ascii"))


def edges_to_nx(edges: list, n: int) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(range(n))
    G.add_edges_from(edges)
    return G


# ---------------------------------------------------------------------------
# GraphStore  (JSON folder)
# ---------------------------------------------------------------------------

class GraphStore:
    """
    Reads and writes the graphs/ folder.
    Each file is a JSON array of {id, sparse6, source, metadata?} records.
    Dedup key is (id, source): same graph from different sources is allowed.
    """

    def __init__(self, graphs_dir: str):
        self.graphs_dir = graphs_dir
        os.makedirs(graphs_dir, exist_ok=True)

    # ── read ──────────────────────────────────────────────────────────────────

    def all_records(self) -> list[dict]:
        """Return all graph records as a flat list (may contain same id with different sources)."""
        records: list[dict] = []
        for path in sorted(glob.glob(os.path.join(self.graphs_dir, "*.json"))):
            with open(path) as f:
                batch = json.load(f)
            records.extend(batch)
        return records

    def all_id_source_pairs(self) -> set[tuple[str, str]]:
        """Return set of (id, source) pairs currently in the store."""
        return {(r["id"], r["source"]) for r in self.all_records()}

    def all_ids(self) -> set[str]:
        """Return set of all unique graph ids (regardless of source)."""
        return {r["id"] for r in self.all_records()}

    def all_sources(self) -> list[str]:
        return sorted({r["source"] for r in self.all_records()})

    # ── write ─────────────────────────────────────────────────────────────────

    def write_batch(self, records: list[dict], filename: str):
        """
        Write records to graphs/{filename}.
        Skips records whose (id, source) pair already exists in the store.
        Returns (written, skipped) counts.
        """
        existing = self.all_id_source_pairs()
        new = [r for r in records if (r["id"], r["source"]) not in existing]
        skipped = len(records) - len(new)
        if new:
            path = os.path.join(self.graphs_dir, filename)
            # Append to existing file if it already exists, else create
            if os.path.exists(path):
                with open(path) as f:
                    current = json.load(f)
                current.extend(new)
                with open(path, "w") as f:
                    json.dump(current, f, indent=2)
            else:
                with open(path, "w") as f:
                    json.dump(new, f, indent=2)
        return len(new), skipped

    def add_graph(self, G, source: str, filename: str, **metadata) -> tuple[str, bool]:
        """
        Compute id + sparse6, write a single record to graphs/{filename}.
        Returns (graph_id, was_new).  was_new=False if (id, source) already exists.
        """
        G = _to_int_graph(G)
        gid, _ = canonical_id(G)
        if (gid, source) in self.all_id_source_pairs():
            return gid, False
        rec = {"id": gid, "sparse6": graph_to_sparse6(G), "source": source}
        if metadata:
            rec["metadata"] = metadata
        self.write_batch([rec], filename)
        return gid, True


# ---------------------------------------------------------------------------
# PropertyCache  (SQLite)
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cache (
    graph_id                TEXT    NOT NULL,
    source                  TEXT    NOT NULL,
    n                       INTEGER NOT NULL,
    m                       INTEGER NOT NULL,
    density                 REAL    NOT NULL,
    d_min                   INTEGER NOT NULL,
    d_max                   INTEGER NOT NULL,
    d_avg                   REAL    NOT NULL,
    d_var                   REAL    NOT NULL,
    degree_sequence         TEXT    NOT NULL,
    is_regular              INTEGER NOT NULL,
    regularity_d            INTEGER,
    is_connected            INTEGER NOT NULL,
    n_components            INTEGER NOT NULL,
    diameter                INTEGER,
    radius                  INTEGER,
    edge_connectivity       INTEGER,
    vertex_connectivity     INTEGER,
    girth                   INTEGER,
    n_triangles             INTEGER NOT NULL,
    avg_clustering          REAL    NOT NULL,
    assortativity           REAL,
    clique_num              INTEGER NOT NULL,
    greedy_chromatic_bound  INTEGER NOT NULL,
    is_k4_free              INTEGER NOT NULL,
    eigenvalues_adj         TEXT    NOT NULL,
    spectral_radius         REAL    NOT NULL,
    spectral_gap            REAL,
    n_distinct_eigenvalues  INTEGER NOT NULL,
    eigenvalues_lap         TEXT    NOT NULL,
    algebraic_connectivity  REAL,
    alpha                   INTEGER NOT NULL,
    c_log                   REAL,
    beta                    REAL,
    turan_density           REAL    NOT NULL,
    mis_vertices            TEXT    NOT NULL,
    triangle_edges          TEXT    NOT NULL,
    triangle_vertices       TEXT    NOT NULL,
    high_degree_vertices    TEXT    NOT NULL,
    metadata                TEXT    NOT NULL DEFAULT '{}',
    PRIMARY KEY (graph_id, source)
);

CREATE INDEX IF NOT EXISTS idx_source   ON cache(source);
CREATE INDEX IF NOT EXISTS idx_n        ON cache(n);
CREATE INDEX IF NOT EXISTS idx_c_log    ON cache(c_log);
CREATE INDEX IF NOT EXISTS idx_alpha    ON cache(alpha);
CREATE INDEX IF NOT EXISTS idx_d_max    ON cache(d_max);
CREATE INDEX IF NOT EXISTS idx_is_k4    ON cache(is_k4_free);
CREATE INDEX IF NOT EXISTS idx_regular  ON cache(is_regular);
"""


class PropertyCache:
    """SQLite-backed property cache. One row per (graph_id, source) pair."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def _migrate(self):
        """Drop old single-PK schema so it gets recreated with composite PK."""
        existing = self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='cache'"
        ).fetchone()
        if existing and "PRIMARY KEY (graph_id, source)" not in existing[0]:
            self._conn.execute("DROP TABLE cache")
            self._conn.commit()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def cached_pairs(self) -> set[tuple[str, str]]:
        """Return set of (graph_id, source) pairs already in the cache."""
        return {(r[0], r[1]) for r in self._conn.execute(
            "SELECT graph_id, source FROM cache"
        )}

    def cached_ids(self) -> set[str]:
        """Return set of unique graph_ids in cache (regardless of source)."""
        return {r[0] for r in self._conn.execute("SELECT DISTINCT graph_id FROM cache")}

    def insert(self, graph_id: str, source: str, props: dict, metadata: dict):
        def j(v):
            return json.dumps(v)

        self._conn.execute("""
            INSERT OR REPLACE INTO cache VALUES (
                ?,?,  ?,?,?,  ?,?,?,?,?,?,?,
                ?,?,?,?,?,?,  ?,?,?,?,  ?,?,?,
                ?,?,?,?,  ?,?,  ?,?,?,?,
                ?,?,?,?,  ?
            )
        """, (
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
            j(props["mis_vertices"]), j(props["triangle_edges"]),
            j(props["triangle_vertices"]), j(props["high_degree_vertices"]),
            j(metadata),
        ))
        self._conn.commit()

    def query(self, **filters) -> list[dict]:
        """
        Filter by any typed column. Values can be scalars or (min, max) tuples.
        Example: cache.query(n=17, is_k4_free=1)
                 cache.query(c_log=(0.0, 0.75), n=(20, 40))
        """
        where, params = [], []
        for col, val in filters.items():
            if isinstance(val, tuple):
                where.append(f"{col} >= ? AND {col} <= ?")
                params.extend(val)
            else:
                where.append(f"{col} = ?")
                params.append(val)
        sql = "SELECT * FROM cache"
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = self._conn.execute(sql, params).fetchall()
        return [self._deserialise(dict(r)) for r in rows]

    def get(self, graph_id: str, source: str | None = None) -> dict | None:
        """Return one cache row. If source is None, returns the first matching row."""
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
        """Return all rows for this graph_id (one per source that discovered it)."""
        rows = self._conn.execute(
            "SELECT * FROM cache WHERE graph_id = ?", (graph_id,)
        ).fetchall()
        return [self._deserialise(dict(r)) for r in rows]

    def all_sources(self) -> list[str]:
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT source FROM cache ORDER BY source"
        )]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]

    @staticmethod
    def _deserialise(row: dict) -> dict:
        for col in ("degree_sequence", "eigenvalues_adj", "eigenvalues_lap",
                    "mis_vertices", "triangle_edges", "triangle_vertices",
                    "high_degree_vertices", "metadata"):
            if isinstance(row.get(col), str):
                row[col] = json.loads(row[col])
        return row


# ---------------------------------------------------------------------------
# GraphDB  (convenience wrapper)
# ---------------------------------------------------------------------------

class GraphDB:
    """
    Combines GraphStore + PropertyCache.
    Call sync() to compute and cache properties for any new (graph, source) pairs.
    """

    def __init__(self, graphs_dir: str, cache_path: str):
        self.store = GraphStore(graphs_dir)
        self.cache = PropertyCache(cache_path)

    def sync(self, show_progress: bool = True):
        """
        Find all (id, source) pairs in the store missing from the cache,
        compute their properties, and insert them.
        """
        from graph_db.properties import compute_properties

        store_recs = self.store.all_records()       # list[dict]
        cached     = self.cache.cached_pairs()      # set of (graph_id, source)

        missing = [r for r in store_recs if (r["id"], r["source"]) not in cached]

        if not missing:
            if show_progress:
                print("Cache up to date.")
            return

        if show_progress:
            print(f"Computing properties for {len(missing)} new graph(s)...")

        for i, rec in enumerate(missing, 1):
            G = sparse6_to_nx(rec["sparse6"])
            props = compute_properties(G)
            self.cache.insert(
                graph_id=rec["id"],
                source=rec["source"],
                props=props,
                metadata=rec.get("metadata", {}),
            )
            if show_progress:
                c = props.get("c_log")
                c_str = f"{c:.4f}" if c else "  —  "
                print(f"  [{i}/{len(missing)}] id={rec['id']} "
                      f"source={rec['source']} n={props['n']} c_log={c_str}")

        if show_progress:
            print(f"Done. Cache now has {self.cache.count()} entries.")

    def close(self):
        self.cache.close()
