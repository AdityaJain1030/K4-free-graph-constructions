"""
utils/pynauty.py
================
Project-wide pynauty availability check, canonical isomorphism-class ids,
and nauty/geng graph utilities.

canonical_id(G) returns (graph_id, canonical_sparse6) where graph_id is
the first 16 hex chars of SHA-256 over the canonical sparse6 produced by
pynauty. pynauty is required — canonical_id raises ImportError if it is
not installed.
"""

import hashlib
import os
import shutil
import subprocess
import tempfile
from itertools import combinations

import networkx as nx

_PYNAUTY_OK: bool | None = None


def has_pynauty() -> bool:
    """Return True if pynauty is importable (result cached after first call)."""
    global _PYNAUTY_OK
    if _PYNAUTY_OK is None:
        try:
            import pynauty  # noqa: F401
            _PYNAUTY_OK = True
        except ImportError:
            _PYNAUTY_OK = False
    return _PYNAUTY_OK


# ---------------------------------------------------------------------------
# Canonical isomorphism-class ids
# ---------------------------------------------------------------------------

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

    graph_id is SHA-256[:16] of the canonical sparse6 produced by pynauty.
    Two isomorphic graphs therefore produce the same id.

    Raises ImportError if pynauty is not installed.
    """
    if not has_pynauty():
        raise ImportError(
            "canonical_id requires pynauty. Install it with "
            "`pip install pynauty` (or via the k4free conda environment)."
        )
    G = _to_int_graph(G)
    cs6 = _canonical_sparse6_pynauty(G)
    return hashlib.sha256(cs6.encode()).hexdigest()[:16], cs6


# ---------------------------------------------------------------------------
# geng helpers
# ---------------------------------------------------------------------------

def find_geng() -> str | None:
    """Return the path to the nauty geng binary, or None if not found."""
    for name in ("geng", "nauty-geng"):
        path = shutil.which(name)
        if path:
            return path
    return None


def graphs_via_geng(geng: str, n: int, flags: str = "-k"):
    """
    Stream all non-isomorphic graphs on n vertices from nauty geng.

    Parameters
    ----------
    geng  : path to the geng binary (from find_geng()).
    n     : number of vertices.
    flags : geng flags string (default '-k' = K4-free).
    """
    with tempfile.NamedTemporaryFile(suffix=".g6", delete=False) as f:
        tmpfile = f.name
    try:
        subprocess.run(
            [geng] + flags.split() + [str(n), tmpfile],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        for G in nx.read_graph6(tmpfile):
            if isinstance(G, nx.Graph):
                yield G
    finally:
        os.unlink(tmpfile)


def graphs_via_python(n: int, k4_free: bool = True):
    """
    Enumerate all non-isomorphic graphs on n vertices via pure Python.
    Feasible only for n ≤ 6.  Uses canonical_id for O(1) isomorphism
    dedup (pynauty canonical sparse6). Requires pynauty.

    Parameters
    ----------
    n       : number of vertices.
    k4_free : if True (default) only yield K4-free graphs.
    """
    from utils.graph_props import is_k4_free_nx

    nodes = list(range(n))
    all_edges = list(combinations(nodes, 2))
    seen_ids: set[str] = set()
    for num_e in range(len(all_edges) + 1):
        for edge_set in combinations(all_edges, num_e):
            G = nx.Graph()
            G.add_nodes_from(nodes)
            G.add_edges_from(edge_set)
            if k4_free and not is_k4_free_nx(G):
                continue
            gid, _ = canonical_id(G)
            if gid in seen_ids:
                continue
            seen_ids.add(gid)
            yield G
