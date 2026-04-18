"""
graph_db/api.py
===============
High-level read API over GraphStore + PropertyCache.
Import this in the visualizer and CLI scripts.
"""

import os

import numpy as np
import networkx as nx

REPO_ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_GRAPHS  = os.path.join(REPO_ROOT, "graphs")
DEFAULT_CACHE   = os.path.join(REPO_ROOT, "cache.db")


class DB:
    """
    Thin read/write façade over GraphStore + PropertyCache.
    Use as a context manager or call .close() when done.

    Parameters
    ----------
    graphs_dir  Path to the graphs/ folder (defaults to repo-root/graphs).
    cache_path  Path to cache.db (defaults to repo-root/cache.db).
    auto_sync   If True, call sync() on open so the cache is up-to-date.
    """

    def __init__(
        self,
        graphs_dir: str = DEFAULT_GRAPHS,
        cache_path: str = DEFAULT_CACHE,
        auto_sync: bool = True,
    ):
        from graph_db.store import GraphDB as _GraphDB
        self._db = _GraphDB(graphs_dir, cache_path)
        if auto_sync:
            self._db.sync(show_progress=False)

    def close(self):
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    # ── queries ───────────────────────────────────────────────────────────────

    def query(self, **filters) -> list[dict]:
        """
        Return cache records matching filters.
        Scalar:  n=17, source='sat_pareto', is_k4_free=1
        Range:   c_log=(0.0, 0.9), n=(20, 40)
        """
        return self._db.cache.query(**filters)

    def get(self, graph_id: str, source: str | None = None) -> dict | None:
        """Return one cache record. If source is None, returns the first match."""
        return self._db.cache.get(graph_id, source)

    def get_all(self, graph_id: str) -> list[dict]:
        """Return all cache rows for this graph_id (one per source)."""
        return self._db.cache.get_all(graph_id)

    def sources(self) -> list[str]:
        """All distinct source tags present in the cache."""
        return self._db.cache.all_sources()

    def count(self) -> int:
        """Total number of cached (graph, source) pairs."""
        return self._db.cache.count()

    # ── helpers ───────────────────────────────────────────────────────────────

    def sparse6_of(self, graph_id: str) -> str | None:
        """Return the sparse6 string for a graph id (same for every source)."""
        for r in self._db.store.all_records():
            if r["id"] == graph_id:
                return r["sparse6"]
        return None

    def load_nx(self, graph_id: str) -> nx.Graph | None:
        """Return a NetworkX Graph for this ID, or None."""
        from graph_db.store import sparse6_to_nx
        s6 = self.sparse6_of(graph_id)
        return sparse6_to_nx(s6) if s6 else None

    def records_with_graphs(self, **filters) -> list[dict]:
        """
        Return cache records augmented with:
          'sparse6'  — raw sparse6 string
          'G'        — networkx.Graph
          'adj'      — numpy uint8 adjacency matrix

        One row per (graph_id, source) pair.  If multiple sources discovered
        the same graph there will be multiple entries with the same graph but
        different source / metadata.
        """
        from graph_db.store import sparse6_to_nx
        # Build id→sparse6 map (same graph → same sparse6 regardless of source)
        sparse6_map = {r["id"]: r["sparse6"] for r in self._db.store.all_records()}
        out = []
        for rec in self.query(**filters):
            s6 = sparse6_map.get(rec["graph_id"])
            if s6 is None:
                continue
            G   = sparse6_to_nx(s6)
            adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
            out.append({**rec, "sparse6": s6, "G": G, "adj": adj})
        return out


# ── module-level convenience functions ────────────────────────────────────────

def open_db(
    graphs_dir: str = DEFAULT_GRAPHS,
    cache_path: str = DEFAULT_CACHE,
    auto_sync: bool = True,
) -> DB:
    """Open and return a DB instance (remember to .close() it or use as context manager)."""
    return DB(graphs_dir, cache_path, auto_sync)


def load_all_graphs(**filters) -> list[dict]:
    """
    One-shot: open DB, load all matching records with G + adj, close DB.
    Suitable for scripts that only need a single pass over the data.
    """
    with open_db() as db:
        return db.records_with_graphs(**filters)
