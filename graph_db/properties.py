"""
graph_db/properties.py
======================
Compute every property that goes into the cache for a given graph.
All values are plain Python types (int, float, list, bool, None).
"""

from math import log

import networkx as nx
import numpy as np

from utils.graph_props import (
    alpha_exact,
    is_k4_free,
    girth,
    triangle_sets,
    c_log_value,
    high_degree_verts,
)


# ---------------------------------------------------------------------------
# Helpers (local to this module)
# ---------------------------------------------------------------------------

def _turan_density(n: int, m: int) -> float:
    if n < 4:
        return 0.0
    q, r = divmod(n, 3)
    sizes = [q + 1] * r + [q] * (3 - r)
    turan_m = (n * n - sum(s * s for s in sizes)) // 2
    return round(m / turan_m, 6) if turan_m else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def compute_properties(G: nx.Graph) -> dict:
    """
    Compute all cache properties for G (nodes must be 0..n-1).
    Returns a dict matching every non-id column in the cache schema.
    """
    n       = G.number_of_nodes()
    m       = G.number_of_edges()
    adj     = nx.to_numpy_array(G, dtype=np.uint8)
    degrees = [int(d) for _, d in G.degree()]

    p: dict = {}

    # --- Basic ---
    p["n"]       = n
    p["m"]       = m
    p["density"] = round(2 * m / (n * (n - 1)), 6) if n > 1 else 0.0

    # --- Degree ---
    p["d_min"]           = int(min(degrees)) if degrees else 0
    p["d_max"]           = int(max(degrees)) if degrees else 0
    p["d_avg"]           = round(float(np.mean(degrees)), 6) if degrees else 0.0
    p["d_var"]           = round(float(np.var(degrees)),  6) if degrees else 0.0
    p["degree_sequence"] = sorted(degrees)
    deg_set              = sorted(set(degrees))
    p["is_regular"]      = len(deg_set) == 1
    p["regularity_d"]    = deg_set[0] if p["is_regular"] else None

    # --- Connectivity ---
    p["is_connected"]  = nx.is_connected(G)
    p["n_components"]  = nx.number_connected_components(G)
    if p["is_connected"] and n > 1:
        p["diameter"]            = nx.diameter(G)
        p["radius"]              = nx.radius(G)
        p["edge_connectivity"]   = nx.edge_connectivity(G)
        p["vertex_connectivity"] = nx.node_connectivity(G)
    else:
        p["diameter"] = p["radius"] = p["edge_connectivity"] = p["vertex_connectivity"] = None

    # --- Cycles / substructure ---
    p["girth"]          = girth(G)
    p["n_triangles"]    = sum(nx.triangles(G).values()) // 3
    p["avg_clustering"] = round(nx.average_clustering(G), 6)
    try:
        a = nx.degree_assortativity_coefficient(G)
        p["assortativity"] = round(float(a), 6) if np.isfinite(a) else None
    except Exception:
        p["assortativity"] = None

    # --- Clique / chromatic ---
    p["clique_num"] = max((len(c) for c in nx.find_cliques(G)), default=0)
    p["greedy_chromatic_bound"] = (
        len(set(nx.greedy_color(G, strategy="largest_first").values())) if n > 0 else 0
    )
    p["is_k4_free"] = bool(is_k4_free(adj))

    # --- Spectral (adjacency) ---
    adj_f = adj.astype(float)
    eig_a = np.sort(np.linalg.eigvalsh(adj_f))[::-1]
    p["eigenvalues_adj"]        = [round(float(e), 6) for e in eig_a]
    p["spectral_radius"]        = round(float(eig_a[0]), 6) if len(eig_a) else None
    p["spectral_gap"]           = round(float(eig_a[0] - eig_a[1]), 6) if len(eig_a) > 1 else None
    p["n_distinct_eigenvalues"] = len({round(float(e), 4) for e in eig_a})

    # --- Spectral (Laplacian) ---
    L     = np.diag(degrees) - adj_f
    eig_l = np.sort(np.linalg.eigvalsh(L))
    p["eigenvalues_lap"]        = [round(float(e), 6) for e in eig_l]
    p["algebraic_connectivity"] = (
        round(float(eig_l[1]), 6) if len(eig_l) > 1 and p["is_connected"] else None
    )

    # --- Independence / extremal ---
    alpha_val, mis_verts = alpha_exact(adj)
    p["alpha"]        = alpha_val
    p["mis_vertices"] = sorted(int(v) for v in mis_verts)

    cv = c_log_value(alpha_val, n, p["d_max"])
    p["c_log"] = round(cv, 6) if cv is not None else None

    # beta: d_avg = (n/alpha) * ln(n/alpha)^beta
    beta = None
    if alpha_val > 0 and n > alpha_val:
        ratio    = n / alpha_val
        ln_ratio = log(ratio)
        if ln_ratio > 1 and p["d_avg"] * alpha_val / n > 0:
            try:
                beta = round(log(p["d_avg"] * alpha_val / n) / log(ln_ratio), 6)
            except Exception:
                pass
    p["beta"] = beta

    # --- Turán ---
    p["turan_density"] = _turan_density(n, m)

    # --- Highlight sets ---
    tri_edges, tri_verts = triangle_sets(G)
    p["triangle_edges"]       = [list(e) for e in tri_edges]
    p["triangle_vertices"]    = tri_verts
    p["high_degree_vertices"] = high_degree_verts(G)

    return p
