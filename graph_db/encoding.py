"""
graph_db/encoding.py
====================
sparse6 / networkx / edge-list conversion utilities.

Canonical ids live in `utils.nauty.canonical_id` — re-exported here for
callers doing `from graph_db.encoding import canonical_id`.
"""

import warnings

import networkx as nx
warnings.filterwarnings("ignore", category=UserWarning, module="networkx")

from utils.nauty import canonical_id, canonical_ids, _to_int_graph  # re-exported


def graph_to_sparse6(G) -> str:
    """Encode G as a sparse6 string (no header). Relabels nodes to 0..n-1 first."""
    G = _to_int_graph(G)
    return nx.to_sparse6_bytes(G, header=False).decode("ascii").strip()


def sparse6_to_nx(s6: str) -> nx.Graph:
    """Decode a sparse6 string into an nx.Graph."""
    return nx.from_sparse6_bytes(s6.encode("ascii"))


def edges_to_nx(edges: list, n: int) -> nx.Graph:
    """Build an nx.Graph on n vertices from an edge list. Isolates preserved."""
    G = nx.Graph()
    G.add_nodes_from(range(n))
    G.add_edges_from(edges)
    return G
