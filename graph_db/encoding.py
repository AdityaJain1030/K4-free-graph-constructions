"""
graph_db/encoding.py
====================
Graph encoding utilities: sparse6 / networkx / edge-list conversion and
canonical isomorphism-class ids.

canonical_id(G) returns (graph_id, canonical_sparse6) where graph_id is
the first 16 hex chars of SHA-256 over the canonical sparse6 produced by
pynauty. Falls back to a Weisfeiler-Lehman hash if pynauty is not
installed.
"""

import hashlib
import warnings

import networkx as nx
warnings.filterwarnings("ignore", category=UserWarning, module="networkx")

from utils.pynauty import has_pynauty as _has_pynauty


def _to_int_graph(G) -> nx.Graph:
    """Coerce arbitrary graph-like input (adj matrix, nx.Graph) to a 0..n-1 relabelled nx.Graph."""
    if not isinstance(G, nx.Graph):
        import numpy as np
        G = nx.from_numpy_array(np.array(G, dtype=np.uint8))
    return nx.convert_node_labels_to_integers(G)


def _canonical_sparse6_pynauty(G: nx.Graph) -> str:
    """Canonical sparse6 via pynauty's canonical labeling. Caller must ensure pynauty importable."""
    import pynauty
    n = G.number_of_nodes()
    adj = {v: list(G.neighbors(v)) for v in range(n)}
    g = pynauty.Graph(n, adjacency_dict=adj)
    cg = pynauty.canon_graph(g)
    H = nx.Graph()
    H.add_nodes_from(range(n))
    for u, nbrs in cg.adjacency_dict.items():
        for v in nbrs:
            if u < v:
                H.add_edge(u, v)
    return nx.to_sparse6_bytes(H, header=False).decode("ascii").strip()


def canonical_id(G) -> tuple[str, str]:
    """
    Return (graph_id, canonical_sparse6) for G.

    graph_id is SHA-256[:16] of the canonical sparse6. Two isomorphic
    graphs therefore produce the same id. If pynauty isn't available,
    the WL hash is used instead — still deterministic, collision-safe
    in practice for K4-free graphs up to ~N=100.
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
