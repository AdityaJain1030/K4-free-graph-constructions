"""
graph_db/properties.py
======================
Compute the full property dict for a graph, matching what visualize.py needs.

All expensive computations happen here once; results go into the cache blob.

Usage
-----
    from graph_db.properties import compute_properties
    from graph_db.store import GraphStore, sparse6_to_nx

    db = GraphStore("graphs.db")
    for gid in db.cache_missing():
        G = db.get_nx(gid)
        props = compute_properties(G)
        db.cache_set(gid, props)
"""

from collections import deque
from math import log

import networkx as nx
import numpy as np

# Optional: exact independence number from project utilities
try:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "SAT_old"))
    from k4free_ilp.alpha_exact import alpha_exact as _alpha_exact
    from k4free_ilp.k4_check import is_k4_free as _is_k4_free
    _HAS_PROJECT_UTILS = True
except ImportError:
    _HAS_PROJECT_UTILS = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _girth(G: nx.Graph) -> int | None:
    girth = float("inf")
    for v in G.nodes():
        dist = {v: 0}
        queue = deque([(v, -1)])
        while queue:
            u, parent = queue.popleft()
            for w in G.neighbors(u):
                if w == parent:
                    continue
                if w in dist:
                    girth = min(girth, dist[u] + dist[w] + 1)
                else:
                    dist[w] = dist[u] + 1
                    queue.append((w, u))
            if girth == 3:
                return 3
    return int(girth) if girth < float("inf") else None


def _triangle_edges_and_verts(G: nx.Graph) -> tuple[list, list]:
    tri_edges, tri_verts = set(), set()
    adj = {v: set(G.neighbors(v)) for v in G.nodes()}
    for u in G.nodes():
        for v in G.neighbors(u):
            if v <= u:
                continue
            common = adj[u] & adj[v]
            for w in common:
                tri_edges.add((min(u, v), max(u, v)))
                tri_edges.add((min(u, w), max(u, w)))
                tri_edges.add((min(v, w), max(v, w)))
                tri_verts.update([u, v, w])
    return sorted(tri_edges), sorted(tri_verts)


def _mis(adj_np: np.ndarray, n: int) -> list[int]:
    """Return one maximum independent set as a list of vertices."""
    if _HAS_PROJECT_UTILS:
        _, verts = _alpha_exact(adj_np)
        return list(verts)
    # Greedy fallback (not exact)
    degrees = adj_np.sum(axis=1)
    order = list(np.argsort(degrees))
    available = set(range(n))
    mis = []
    for v in order:
        if v in available:
            mis.append(v)
            available -= set(np.where(adj_np[v])[0]) | {v}
    return mis


def _turan_density(G: nx.Graph) -> float:
    """
    Turán density: ratio of edges to the Turán bound ex(n, K4).
    Turán bound for K4-free graphs: ex(n, K4) = |E(T(n,3))| = floor(n²·2/9·...).
    Uses the exact formula: floor(n/3)·ceil(n/3)·... but simplified as
    (2/3)·(n²/2) for large n. We use the exact Turán number.
    """
    n = G.number_of_nodes()
    m = G.number_of_edges()
    if n < 4:
        return 0.0
    # Turán graph T(n,3): 3 parts as equal as possible
    q, r = divmod(n, 3)
    # r parts of size q+1, (3-r) parts of size q
    # |E(T(n,3))| = n² - (q+1)²·r - q²·(3-r)) / 2 ... easier:
    part_sizes = [q + 1] * r + [q] * (3 - r)
    turan_edges = (n * n - sum(s * s for s in part_sizes)) // 2
    if turan_edges == 0:
        return 0.0
    return m / turan_edges


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_properties(G: nx.Graph, meta: dict | None = None) -> dict:
    """
    Compute all cached properties for a graph.

    Parameters
    ----------
    G     : NetworkX graph (nodes 0..n-1)
    meta  : optional dict of already-known fields (e.g. alpha, d_max, c_log
            from the SAT solver) to skip recomputation where possible

    Returns
    -------
    dict with all properties listed below.  All values are plain Python
    types (int, float, list, bool, None) — safe to pickle and to JSON-dump.
    """
    meta = meta or {}
    n = G.number_of_nodes()
    m = G.number_of_edges()
    adj = nx.to_numpy_array(G, dtype=np.uint8)
    degrees = [d for _, d in G.degree()]

    props: dict = {}

    # --- Basic ---
    props["n"] = n
    props["m"] = m
    props["density"] = round(2 * m / (n * (n - 1)), 6) if n > 1 else 0.0
    props["d_min"] = int(min(degrees)) if degrees else 0
    props["d_max"] = int(max(degrees)) if degrees else 0
    props["d_avg"] = round(float(np.mean(degrees)), 4) if degrees else 0.0
    props["d_var"] = round(float(np.var(degrees)), 4) if degrees else 0.0
    props["degree_sequence"] = sorted(degrees)
    deg_set = sorted(set(degrees))
    props["is_regular"] = len(deg_set) == 1
    props["regularity_d"] = deg_set[0] if props["is_regular"] else None

    # --- Connectivity ---
    props["is_connected"] = nx.is_connected(G)
    props["n_components"] = nx.number_connected_components(G)
    if props["is_connected"] and n > 1:
        props["diameter"] = nx.diameter(G)
        props["radius"] = nx.radius(G)
        props["edge_connectivity"] = nx.edge_connectivity(G)
        props["vertex_connectivity"] = nx.node_connectivity(G)
    else:
        props["diameter"] = None
        props["radius"] = None
        props["edge_connectivity"] = None
        props["vertex_connectivity"] = None

    # --- Cycles ---
    props["girth"] = _girth(G)

    # --- Substructure ---
    props["n_triangles"] = sum(nx.triangles(G).values()) // 3
    props["avg_clustering"] = round(nx.average_clustering(G), 6)
    try:
        props["assortativity"] = round(nx.degree_assortativity_coefficient(G), 6)
    except Exception:
        props["assortativity"] = None

    props["clique_num"] = max(
        (len(c) for c in nx.find_cliques(G)), default=0
    )
    props["greedy_chromatic_bound"] = len(
        set(nx.greedy_color(G, strategy="largest_first").values())
    ) if n > 0 else 0

    # --- K4-freeness ---
    if _HAS_PROJECT_UTILS:
        props["is_k4_free"] = bool(_is_k4_free(adj))
    else:
        props["is_k4_free"] = props["clique_num"] < 4

    # --- Spectral ---
    adj_f = adj.astype(float)
    eig_adj = np.sort(np.linalg.eigvalsh(adj_f))[::-1]
    eig_adj_list = [round(float(e), 6) for e in eig_adj]
    props["eigenvalues_adj"] = eig_adj_list
    props["spectral_radius"] = eig_adj_list[0] if eig_adj_list else None
    props["spectral_gap"] = round(eig_adj_list[0] - eig_adj_list[1], 6) if len(eig_adj_list) > 1 else None
    props["n_distinct_eigenvalues"] = len(set(round(e, 4) for e in eig_adj_list))

    L = np.diag(degrees) - adj_f
    eig_lap = np.sort(np.linalg.eigvalsh(L))
    props["eigenvalues_lap"] = [round(float(e), 6) for e in eig_lap]
    props["algebraic_connectivity"] = round(float(eig_lap[1]), 6) if len(eig_lap) > 1 else None

    # --- Independence ---
    alpha = meta.get("alpha")
    if alpha is None:
        mis_verts = _mis(adj, n)
        alpha = len(mis_verts)
    else:
        mis_verts = _mis(adj, n)  # still compute the actual vertex set
    props["alpha"] = int(alpha)
    props["mis_vertices"] = sorted(int(v) for v in mis_verts)

    # --- c_log ---
    d_max = props["d_max"]
    c_log = meta.get("c_log")
    if c_log is None and d_max > 1:
        c_log = round(alpha * d_max / (n * log(d_max)), 6)
    props["c_log"] = c_log

    # --- Turán ---
    props["turan_density"] = round(_turan_density(G), 6)

    # --- Highlights (for visualizer) ---
    tri_edges, tri_verts = _triangle_edges_and_verts(G)
    props["triangle_edges"] = tri_edges
    props["triangle_vertices"] = tri_verts
    props["high_degree_vertices"] = [
        int(v) for v, d in G.degree() if d == d_max
    ]

    return props
