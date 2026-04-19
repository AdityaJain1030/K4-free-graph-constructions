"""
graph_db — graph store + property cache for the K4-free project.

Most callers only need the DB class:

    from graph_db import DB

    with DB() as db:
        rows = db.query(source="sat_pareto", ranges={"c_log": (0, 0.75)})

See DESIGN.md for the full architecture.
"""

from graph_db.db import DB, open_db, load_all_graphs, DEFAULT_GRAPHS, DEFAULT_CACHE
from graph_db.encoding import (
    canonical_id,
    graph_to_sparse6,
    sparse6_to_nx,
    edges_to_nx,
)
from graph_db.properties import compute_properties
from graph_db.store import GraphStore
from graph_db.cache import PropertyCache

__all__ = [
    # primary public surface
    "DB", "open_db", "load_all_graphs",
    "DEFAULT_GRAPHS", "DEFAULT_CACHE",
    # encoding helpers (producers use these directly)
    "canonical_id", "graph_to_sparse6", "sparse6_to_nx", "edges_to_nx",
    # property computation (producers rarely need this)
    "compute_properties",
    # low-level stores (testing / advanced use)
    "GraphStore", "PropertyCache",
]
