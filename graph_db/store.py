"""
graph_db/store.py
=================
Graph storage and property cache backed by SQLite.

Schema design
-------------
graphs table
    id       TEXT PRIMARY KEY  -- 16-hex canonical hash (see _canonical_id)
    sparse6  TEXT NOT NULL     -- canonical sparse6 string
    n        INT               -- vertex count (indexed for fast filter)
    m        INT               -- edge count
    meta     TEXT              -- JSON blob for all optional fields (source, c_log, etc.)
                               -- adding new optional fields never requires ALTER TABLE

cache table
    graph_id TEXT PRIMARY KEY  -- references graphs.id
    data     BLOB              -- pickle of dict {property_name: value}
                               -- adding new properties never requires ALTER TABLE

Deduplication
-------------
Graphs are identified by the isomorphism class, not vertex labelling.
Canonical ID is computed as SHA-256[:16] of the canonical sparse6.

Canonical sparse6 is produced by:
  1. pynauty  (Linux/Mac with nauty binary) -- true canonical labelling
  2. WL hash fallback -- Weisfeiler-Lehman graph hash from networkx
     Not 100% collision-free for non-isomorphic graphs, but in practice
     reliable for K4-free graphs up to N~100. On hash collision the store
     runs a VF2 isomorphism check to confirm.

Usage
-----
    from graph_db.store import GraphStore

    db = GraphStore("graphs.db")
    gid, is_new = db.add(G, source="sat_pareto", alpha=3, d_max=8, c_log=0.679)
    gid, is_new = db.add(G2)  # deduplication: returns existing id if isomorphic

    graph = db.get(gid)          # returns {"id", "sparse6", "n", "m", **meta}
    graphs = db.query(n=17)      # filter by any indexed field
    graphs = db.all_n()          # list of distinct n values in store

    db.cache_set(gid, props)     # store computed property dict
    props = db.cache_get(gid)    # retrieve; None if not cached
    db.cache_invalidate(gid)     # force recompute next time
"""

import hashlib
import json
import pickle
import sqlite3
from contextlib import contextmanager
from typing import Any

import networkx as nx


# ---------------------------------------------------------------------------
# Canonical form
# ---------------------------------------------------------------------------

def _to_nx(G_or_adj):
    """Accept a networkx Graph or numpy adjacency matrix."""
    if isinstance(G_or_adj, nx.Graph):
        return nx.convert_node_labels_to_integers(G_or_adj)
    import numpy as np
    return nx.from_numpy_array(np.array(G_or_adj, dtype=np.uint8))


def _canonical_sparse6_pynauty(G: nx.Graph) -> str:
    """Use pynauty for a true canonical labelling → canonical sparse6."""
    import pynauty
    n = G.number_of_nodes()
    adj = {v: list(G.neighbors(v)) for v in range(n)}
    g = pynauty.Graph(n, adjacency_dict=adj)
    cert = pynauty.certificate(g)
    # cert is a byte string that is a canonical adjacency encoding;
    # reconstruct graph from certificate and serialise as sparse6
    H = _cert_to_nx(cert, n)
    return nx.to_sparse6_bytes(H, header=False).decode("ascii").strip()


def _cert_to_nx(cert: bytes, n: int) -> nx.Graph:
    """Reconstruct a graph from a pynauty certificate byte string."""
    H = nx.Graph()
    H.add_nodes_from(range(n))
    bit_idx = 0
    for i in range(n):
        for j in range(i + 1, n):
            byte_pos = bit_idx // 8
            bit_pos = 7 - (bit_idx % 8)
            if byte_pos < len(cert) and (cert[byte_pos] >> bit_pos) & 1:
                H.add_edge(i, j)
            bit_idx += 1
    return H


def _canonical_sparse6_wl(G: nx.Graph) -> str:
    """
    WL-hash-based canonical ID fallback (no nauty required).

    Produces a stable string identifier for the isomorphism class using
    Weisfeiler-Lehman graph hashing. Not guaranteed collision-free for
    non-isomorphic graphs, but reliable in practice for this graph family.

    Returns the WL hash string (not a sparse6 — used only for ID derivation).
    """
    return nx.weisfeiler_lehman_graph_hash(G, iterations=6)


_PYNAUTY_AVAILABLE: bool | None = None


def _has_pynauty() -> bool:
    global _PYNAUTY_AVAILABLE
    if _PYNAUTY_AVAILABLE is None:
        try:
            import pynauty  # noqa: F401
            _PYNAUTY_AVAILABLE = True
        except ImportError:
            _PYNAUTY_AVAILABLE = False
    return _PYNAUTY_AVAILABLE


def canonical_id(G: nx.Graph) -> tuple[str, str]:
    """
    Return (graph_id, canonical_sparse6) for G.

    graph_id is a 16-hex-char content hash of the isomorphism class.
    canonical_sparse6 is the canonical sparse6 string (or WL hash string
    when pynauty is unavailable).
    """
    G = _to_nx(G)
    if _has_pynauty():
        try:
            cs6 = _canonical_sparse6_pynauty(G)
            gid = hashlib.sha256(cs6.encode()).hexdigest()[:16]
            return gid, cs6
        except Exception:
            pass
    # Fallback: WL hash
    wl = _canonical_sparse6_wl(G)
    gid = hashlib.sha256(wl.encode()).hexdigest()[:16]
    return gid, wl


def graph_to_sparse6(G: nx.Graph) -> str:
    """Serialise G as a sparse6 string (current labelling, not canonical)."""
    return nx.to_sparse6_bytes(G, header=False).decode("ascii").strip()


def sparse6_to_nx(s6: str) -> nx.Graph:
    return nx.from_sparse6_bytes(s6.encode("ascii"))


# ---------------------------------------------------------------------------
# GraphStore
# ---------------------------------------------------------------------------

class GraphStore:
    """
    SQLite-backed graph store with integrated property cache.

    Parameters
    ----------
    db_path : str
        Path to the SQLite database file. Created on first use.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def close(self):
        self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _init_schema(self):
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS graphs (
                id      TEXT PRIMARY KEY,
                sparse6 TEXT NOT NULL,
                n       INT,
                m       INT,
                meta    TEXT DEFAULT '{}'
            );
            CREATE INDEX IF NOT EXISTS idx_graphs_n ON graphs(n);

            CREATE TABLE IF NOT EXISTS cache (
                graph_id TEXT PRIMARY KEY,
                data     BLOB
            );
        """)
        self._conn.commit()

    # ------------------------------------------------------------------
    # Graph CRUD
    # ------------------------------------------------------------------

    def add(self, G, **meta) -> tuple[str, bool]:
        """
        Insert G into the store.  Returns (graph_id, was_new).

        If an isomorphic graph is already stored, returns its existing id
        and was_new=False without modifying the database.

        Optional keyword args are stored in the JSON meta blob:
            source, c_log, alpha, d_max, source_meta, ...
        """
        G = _to_nx(G)
        gid, cs6 = canonical_id(G)

        # Check for existing entry (dedup)
        row = self._conn.execute(
            "SELECT id FROM graphs WHERE id = ?", (gid,)
        ).fetchone()

        if row is not None:
            # If pynauty is unavailable, verify isomorphism on WL collision
            if not _has_pynauty():
                existing = self.get(gid)
                G_existing = sparse6_to_nx(existing["sparse6"])
                if not nx.is_isomorphic(G, G_existing):
                    # True WL collision (extremely rare): append suffix
                    suffix = 0
                    while True:
                        candidate = f"{gid}_{suffix:02x}"
                        if not self._conn.execute(
                            "SELECT id FROM graphs WHERE id = ?", (candidate,)
                        ).fetchone():
                            gid = candidate
                            break
                        suffix += 1
                else:
                    return gid, False
            else:
                return gid, False

        n = G.number_of_nodes()
        m = G.number_of_edges()
        s6 = graph_to_sparse6(G)

        self._conn.execute(
            "INSERT INTO graphs(id, sparse6, n, m, meta) VALUES (?,?,?,?,?)",
            (gid, s6, n, m, json.dumps(meta)),
        )
        self._conn.commit()
        return gid, True

    def get(self, graph_id: str) -> dict | None:
        """Return graph record as dict, or None if not found."""
        row = self._conn.execute(
            "SELECT id, sparse6, n, m, meta FROM graphs WHERE id = ?",
            (graph_id,),
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["meta"] = json.loads(d["meta"])
        return d

    def get_nx(self, graph_id: str) -> nx.Graph | None:
        """Return the stored graph as a NetworkX Graph."""
        row = self.get(graph_id)
        if row is None:
            return None
        return sparse6_to_nx(row["sparse6"])

    def query(self, n: int | None = None, **meta_filters) -> list[dict]:
        """
        Filter graphs by n and/or meta fields.

        meta_filters are matched exactly against the JSON meta blob.
        Example: db.query(n=17, source="sat_pareto")
        """
        sql = "SELECT id, sparse6, n, m, meta FROM graphs WHERE 1=1"
        params: list[Any] = []
        if n is not None:
            sql += " AND n = ?"
            params.append(n)
        rows = self._conn.execute(sql, params).fetchall()
        results = []
        for row in rows:
            d = dict(row)
            d["meta"] = json.loads(d["meta"])
            if all(d["meta"].get(k) == v for k, v in meta_filters.items()):
                results.append(d)
        return results

    def all_ids(self) -> list[str]:
        return [r[0] for r in self._conn.execute("SELECT id FROM graphs").fetchall()]

    def all_n(self) -> list[int]:
        """Return sorted list of distinct n values in the store."""
        return [r[0] for r in self._conn.execute(
            "SELECT DISTINCT n FROM graphs ORDER BY n"
        ).fetchall()]

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM graphs").fetchone()[0]

    def update_meta(self, graph_id: str, **updates):
        """Merge new key-value pairs into a graph's meta blob."""
        row = self._conn.execute(
            "SELECT meta FROM graphs WHERE id = ?", (graph_id,)
        ).fetchone()
        if row is None:
            raise KeyError(graph_id)
        meta = json.loads(row["meta"])
        meta.update(updates)
        self._conn.execute(
            "UPDATE graphs SET meta = ? WHERE id = ?",
            (json.dumps(meta), graph_id),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    # Property cache
    # ------------------------------------------------------------------

    def cache_set(self, graph_id: str, props: dict):
        """Store a property dict for graph_id. Overwrites existing entry."""
        data = pickle.dumps(props, protocol=pickle.HIGHEST_PROTOCOL)
        self._conn.execute(
            "INSERT OR REPLACE INTO cache(graph_id, data) VALUES (?,?)",
            (graph_id, data),
        )
        self._conn.commit()

    def cache_get(self, graph_id: str) -> dict | None:
        """Return cached property dict, or None if not yet computed."""
        row = self._conn.execute(
            "SELECT data FROM cache WHERE graph_id = ?", (graph_id,)
        ).fetchone()
        if row is None:
            return None
        return pickle.loads(row["data"])

    def cache_invalidate(self, graph_id: str):
        """Delete cached properties for graph_id (forces recompute)."""
        self._conn.execute("DELETE FROM cache WHERE graph_id = ?", (graph_id,))
        self._conn.commit()

    def cache_missing(self) -> list[str]:
        """Return ids of graphs that have no cache entry."""
        return [r[0] for r in self._conn.execute("""
            SELECT g.id FROM graphs g
            LEFT JOIN cache c ON g.id = c.graph_id
            WHERE c.graph_id IS NULL
        """).fetchall()]

    def cache_update(self, graph_id: str, **updates):
        """Merge new keys into an existing cache entry without full recompute."""
        existing = self.cache_get(graph_id) or {}
        existing.update(updates)
        self.cache_set(graph_id, existing)
