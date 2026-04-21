"""
utils/nauty.py
==============
Canonical isomorphism-class ids via nauty's `labelg` CLI, plus helpers
for enumerating graphs via `geng`.

`canonical_id(G)` returns `(graph_id, canonical_sparse6)` where
`graph_id` is the first 16 hex chars of SHA-256 over the canonical
sparse6 of G. Two isomorphic graphs produce the same id.

The implementation shells out to nauty's `labelg` (same binary set as
`geng`, built by `scripts/setup_nauty.sh`). There is no Python-extension
dependency: one `labelg` subprocess per call, or one per batch via
`canonical_ids`. The CLI reads graph6 on stdin and writes canonical
graph6 on stdout, one graph per line.
"""

import hashlib
import os
import shutil
import subprocess
import tempfile
from itertools import combinations

import networkx as nx


# ---------------------------------------------------------------------------
# Binary discovery
# ---------------------------------------------------------------------------

_LABELG_CACHED: str | None = None


def _find_labelg() -> str:
    """Locate labelg on PATH. Cached after first lookup."""
    global _LABELG_CACHED
    if _LABELG_CACHED is not None:
        return _LABELG_CACHED
    for name in ("labelg", "nauty-labelg"):
        path = shutil.which(name)
        if path:
            _LABELG_CACHED = path
            return path
    raise RuntimeError(
        "labelg not found on PATH. Install nauty via `bash scripts/setup_nauty.sh` "
        "inside the activated k4free env."
    )


# ---------------------------------------------------------------------------
# Canonical ids
# ---------------------------------------------------------------------------

def _to_int_graph(G) -> nx.Graph:
    """Coerce arbitrary graph-like input (adj matrix, nx.Graph, DiGraph) to a 0..n-1 relabelled undirected nx.Graph."""
    if not isinstance(G, nx.Graph):
        import numpy as np
        G = nx.from_numpy_array(np.array(G, dtype=np.uint8))
    if G.is_directed():
        G = G.to_undirected()
    return nx.convert_node_labels_to_integers(G)


def _sparse6_from_canonical_graph6(canon_g6: bytes) -> str:
    """Decode a canonical graph6 line from labelg and re-encode as header-less sparse6."""
    H = nx.from_graph6_bytes(canon_g6.strip())
    return nx.to_sparse6_bytes(H, header=False).decode("ascii").strip()


def _labelg_batch(g6_lines: list[bytes]) -> list[bytes]:
    """
    Feed `g6_lines` (one graph6 per entry, no trailing newline) to labelg
    and return the canonical graph6 output lines in the same order.

    labelg's `-g` forces graph6 output; `-q` suppresses the progress
    messages it normally prints to stderr.
    """
    labelg = _find_labelg()
    inp = b"\n".join(g6_lines) + b"\n"
    r = subprocess.run(
        [labelg, "-qg"],
        input=inp,
        capture_output=True,
        check=True,
    )
    out_lines = [ln for ln in r.stdout.split(b"\n") if ln]
    if len(out_lines) != len(g6_lines):
        raise RuntimeError(
            f"labelg emitted {len(out_lines)} lines for {len(g6_lines)} inputs"
        )
    return out_lines


def canonical_id(G) -> tuple[str, str]:
    """
    Return (graph_id, canonical_sparse6) for G.

    graph_id is SHA-256[:16] of the canonical sparse6 produced by nauty's
    labelg. Two isomorphic graphs therefore produce the same id.
    """
    G = _to_int_graph(G)
    g6 = nx.to_graph6_bytes(G, header=False).strip()
    canon_g6 = _labelg_batch([g6])[0]
    cs6 = _sparse6_from_canonical_graph6(canon_g6)
    return hashlib.sha256(cs6.encode()).hexdigest()[:16], cs6


def canonical_ids(graphs) -> list[tuple[str, str]]:
    """
    Batched canonical_id. One labelg subprocess for the whole list;
    amortises the fork+exec cost across many graphs.
    """
    graphs = [_to_int_graph(G) for G in graphs]
    if not graphs:
        return []
    g6s = [nx.to_graph6_bytes(G, header=False).strip() for G in graphs]
    canon_g6s = _labelg_batch(g6s)
    out: list[tuple[str, str]] = []
    for canon in canon_g6s:
        cs6 = _sparse6_from_canonical_graph6(canon)
        out.append((hashlib.sha256(cs6.encode()).hexdigest()[:16], cs6))
    return out


def canonical_graph(G) -> nx.Graph:
    """
    Return the canonically-labelled version of G as an nx.Graph.

    Useful when a caller wants the canonical *edge set* (e.g. for Jaccard
    similarity between iso-classes), not just the id.
    """
    G = _to_int_graph(G)
    g6 = nx.to_graph6_bytes(G, header=False).strip()
    canon_g6 = _labelg_batch([g6])[0]
    return nx.from_graph6_bytes(canon_g6.strip())


# ---------------------------------------------------------------------------
# geng helpers (unchanged — already subprocess-based)
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
    dedup.

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
