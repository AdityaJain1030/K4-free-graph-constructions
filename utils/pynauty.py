"""
utils/pynauty.py
================
Project-wide pynauty availability check and nauty/geng graph utilities.
"""

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
        yield from nx.read_graph6(tmpfile)
    finally:
        os.unlink(tmpfile)


def graphs_via_python(n: int, k4_free: bool = True):
    """
    Enumerate all non-isomorphic graphs on n vertices via pure Python.
    Feasible only for n ≤ 6.  Uses canonical_id for O(1) isomorphism dedup
    (pynauty certificate when available, WL hash otherwise).

    Parameters
    ----------
    n       : number of vertices.
    k4_free : if True (default) only yield K4-free graphs.
    """
    from graph_db.store import canonical_id
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
