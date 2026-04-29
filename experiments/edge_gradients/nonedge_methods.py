"""
experiments/edge_gradients/nonedge_methods.py
=============================================
Per-non-edge attribution methods for "which non-edge to add to lower α."

Each method takes (G, non_edges) and returns dict {edge -> score} where
HIGHER score means "this addition is more likely to lower α."

Methods:
  random            — uniform tie-breaking baseline.
  drop_alpha        — exact: α(G) − α(G + e). ≥ 0 always.
  drop_e_max        — global hard-core analogue: E_max(G) − E_max(G + e).
  drop_l_hc         — local hard-core analogue: L_HC(G) − L_HC(G + e).
  hardcore_comarg   — ρ_uw(G, λ) = λ² Z(G − N[u] − N[w], λ) / Z(G, λ).
                       The hard-core probability that u and w both lie in
                       a randomly drawn IS. High = adding uw disrupts the
                       most IS support.
  sdp_X_uw          — X_uw at Lovász ϑ optimum. Lovász's "co-occurrence"
                       in the SDP relaxation. High = SDP wants u, w to
                       jointly carry weight, so forbidding the pair via
                       a new edge tightens the bound.
  lp_xu_plus_xw     — max(0, x_u + x_w − 1) at LP-α optimum. The LP
                       slack the new edge constraint would remove.
  hoffman_grad      — w[u] w[w] from λ_min eigenvector (regular graphs).
                       Returns None if not regular or λ_min is degenerate.
"""
from __future__ import annotations

import itertools
import math
import os
import sys

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from utils.alpha_bounds import (  # noqa: E402
    hardcore_alpha, hardcore_local,
    _independence_polynomial, _log_poly_eval,
)
from utils.graph_props import alpha_bb_clique_cover_nx as alpha_nx, is_k4_free  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def safe_non_edges(G: nx.Graph) -> list[tuple[int, int]]:
    """All non-edges (u, v) such that G + uv stays K4-free."""
    out = []
    nodes = list(G.nodes())
    for u, v in itertools.combinations(nodes, 2):
        if G.has_edge(u, v):
            continue
        H = G.copy()
        H.add_edge(u, v)
        if is_k4_free(nx.to_numpy_array(H, dtype=np.uint8)):
            out.append((min(u, v), max(u, v)))
    return out


# ---------------------------------------------------------------------------
# 1. Random
# ---------------------------------------------------------------------------

def random_score(G, non_edges, rng=None):
    if rng is None:
        rng = np.random.default_rng()
    return {e: float(rng.random()) for e in non_edges}


# ---------------------------------------------------------------------------
# 2. drop_alpha (exact)
# ---------------------------------------------------------------------------

def drop_alpha_score(G, non_edges):
    base, _ = alpha_nx(G)
    out = {}
    for e in non_edges:
        H = G.copy()
        H.add_edge(*e)
        a, _ = alpha_nx(H)
        out[e] = float(base - a)
    return out


# ---------------------------------------------------------------------------
# 3. drop_e_max
# ---------------------------------------------------------------------------

def drop_e_max_score(G, non_edges):
    base = hardcore_alpha(G).e_max
    out = {}
    for e in non_edges:
        H = G.copy()
        H.add_edge(*e)
        out[e] = float(base - hardcore_alpha(H).e_max)
    return out


# ---------------------------------------------------------------------------
# 4. drop_l_hc
# ---------------------------------------------------------------------------

def drop_l_hc_score(G, non_edges):
    base = hardcore_local(G).e_max
    out = {}
    for e in non_edges:
        H = G.copy()
        H.add_edge(*e)
        out[e] = float(base - hardcore_local(H).e_max)
    return out


# ---------------------------------------------------------------------------
# 5. hardcore_comarg  —  ρ_uw at fugacity λ
# ---------------------------------------------------------------------------

def hardcore_comarg_score(G, non_edges, lam: float = 10.0):
    """
    ρ_uw(G, λ) = λ² · Z(G − N[u] − N[w], λ) / Z(G, λ).

    Per-step cost: 1 polynomial of G plus 1 polynomial of each induced
    subgraph G − N[u] − N[w] (cheap because that subgraph is small).
    """
    Z_G = _independence_polynomial(G)
    log_Z_G = _log_poly_eval(Z_G, lam)
    log_lam = math.log(lam)
    out = {}
    for (u, w) in non_edges:
        keep = set(G.nodes()) - ({u, w} | set(G.neighbors(u)) | set(G.neighbors(w)))
        H = G.subgraph(keep).copy()
        Z_H = _independence_polynomial(H)
        log_Z_H = _log_poly_eval(Z_H, lam)
        out[(u, w)] = float(math.exp(2 * log_lam + log_Z_H - log_Z_G))
    return out


# ---------------------------------------------------------------------------
# 6. SDP X_uw at Lovász ϑ optimum
# ---------------------------------------------------------------------------

def sdp_X_uw_score(G, non_edges):
    """
    X_uw at the optimum of  max ⟨J, X⟩  s.t. X ⪰ 0, tr X = 1, X_ij = 0 for ij ∈ E.
    Higher X_uw = the SDP wants u, w to carry joint weight, so forbidding
    that via a new edge would bite.
    """
    try:
        import cvxpy as cp
    except ImportError:
        return None
    A = nx.to_numpy_array(G, dtype=np.uint8)
    n = A.shape[0]
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    X = cp.Variable((n, n), symmetric=True)
    cons = [X >> 0, cp.trace(X) == 1]
    iu, ju = np.where(np.triu(A, 1) > 0)
    for i, j in zip(iu, ju):
        cons.append(X[i, j] == 0)
    prob = cp.Problem(cp.Maximize(cp.sum(X)), cons)
    prob.solve(solver="SCS", verbose=False)
    if prob.status not in ("optimal", "optimal_inaccurate"):
        return None
    Xv = X.value
    return {(u, w): float(Xv[idx[u], idx[w]]) for (u, w) in non_edges}


# ---------------------------------------------------------------------------
# 7. LP slack on the would-be new edge constraint
# ---------------------------------------------------------------------------

def lp_xu_plus_xw_score(G, non_edges):
    """
    Solve  max Σ x_v  s.t. x_u + x_v ≤ 1 ∀ uv ∈ E,  x ∈ [0, 1]^V.
    Score for non-edge (u, w) = max(0, x_u + x_w − 1) = the slack the
    new constraint would remove. Zero if the LP solution already
    respects the would-be constraint.
    """
    try:
        import cvxpy as cp
    except ImportError:
        return None
    n = G.number_of_nodes()
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    x = cp.Variable(n)
    cons = [x >= 0, x <= 1]
    for (u, v) in G.edges():
        cons.append(x[idx[u]] + x[idx[v]] <= 1)
    prob = cp.Problem(cp.Maximize(cp.sum(x)), cons)
    prob.solve(solver="SCS", verbose=False)
    if prob.status not in ("optimal", "optimal_inaccurate"):
        return None
    xv = x.value
    return {
        (u, w): float(max(0.0, xv[idx[u]] + xv[idx[w]] - 1.0))
        for (u, w) in non_edges
    }


# ---------------------------------------------------------------------------
# 8. Hoffman gradient  (regular graphs only)
# ---------------------------------------------------------------------------

def hoffman_grad_score(G, non_edges):
    """
    For d-regular G with non-degenerate λ_min, ∂λ_min/∂A_uw = 2·w[u]·w[w].
    Adding edge with w[u] w[w] > 0 raises λ_min toward 0, which lowers H.
    Score: w[u] · w[w] (higher = better Hoffman drop).
    Returns None if not regular or λ_min is degenerate.
    """
    A = nx.to_numpy_array(G, dtype=float)
    deg = A.sum(axis=1)
    if not np.allclose(deg, deg[0]):
        return None
    w_all, V = np.linalg.eigh(A)
    if abs(w_all[1] - w_all[0]) < 1e-6:
        return None
    w = V[:, 0]
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    return {(u, ww): float(w[idx[u]] * w[idx[ww]]) for (u, ww) in non_edges}


METHODS = {
    "random":          random_score,
    "drop_alpha":      drop_alpha_score,
    "drop_e_max":      drop_e_max_score,
    "drop_l_hc":       drop_l_hc_score,
    "hardcore_comarg": hardcore_comarg_score,
    "sdp_X_uw":        sdp_X_uw_score,
    "lp_xu_plus_xw":   lp_xu_plus_xw_score,
    "hoffman_grad":    hoffman_grad_score,
}
