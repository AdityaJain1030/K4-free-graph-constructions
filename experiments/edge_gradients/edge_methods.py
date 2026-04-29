"""
experiments/edge_gradients/edge_methods.py
==========================================
Per-edge attribution methods for α(G). Each method returns a dict
{edge -> score} with edges as sorted tuples (u, v).

Methods:
  drop_alpha     — exact: α(G − e) − α(G), the gold-standard contribution.
  drop_e_max     — global hard-core analogue: E_max(G − e) − E_max(G).
  drop_l_hc      — local hard-core analogue: L_HC(G − e) − L_HC(G).
  lp_dual        — LP relaxation of α: dual multiplier on the constraint
                   x_u + x_v ≤ 1.
  sdp_dual       — Lovász ϑ SDP: dual multiplier on the constraint X_uv = 0.
  hoffman_grad   — for d-regular G, ∂H/∂A_uv via Hellmann–Feynman on λ_min.

Convention: "higher score" = "this edge matters more to α." For the
drop_* methods, score = α(G−e) − α(G) ≥ 0; for LP/SDP duals, score is
the multiplier magnitude (always ≥ 0); for Hoffman gradient we report
the absolute change in H per unit edge weight.
"""
from __future__ import annotations

import os
import sys

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from utils.alpha_bounds import hardcore_alpha, hardcore_local  # noqa: E402
from utils.graph_props import alpha_bb_clique_cover_nx as alpha_nx  # noqa: E402


def _edges(G: nx.Graph) -> list[tuple[int, int]]:
    return [tuple(sorted(e)) for e in G.edges()]


# ---------------------------------------------------------------------------
# 1. Drop-α (exact gold standard)
# ---------------------------------------------------------------------------

def drop_alpha(G: nx.Graph) -> dict[tuple[int, int], int]:
    """For each edge e, α(G − e) − α(G). Always ≥ 0."""
    base, _ = alpha_nx(G)
    out: dict[tuple[int, int], int] = {}
    for e in _edges(G):
        H = G.copy()
        H.remove_edge(*e)
        a, _ = alpha_nx(H)
        out[e] = a - base
    return out


# ---------------------------------------------------------------------------
# 2. Drop-E_max (global hard-core)
# ---------------------------------------------------------------------------

def drop_e_max(G: nx.Graph) -> dict[tuple[int, int], float]:
    base = hardcore_alpha(G).e_max
    out: dict[tuple[int, int], float] = {}
    for e in _edges(G):
        H = G.copy()
        H.remove_edge(*e)
        out[e] = hardcore_alpha(H).e_max - base
    return out


# ---------------------------------------------------------------------------
# 3. Drop-L_HC (local hard-core)
# ---------------------------------------------------------------------------

def drop_l_hc(G: nx.Graph) -> dict[tuple[int, int], float]:
    base = hardcore_local(G).e_max
    out: dict[tuple[int, int], float] = {}
    for e in _edges(G):
        H = G.copy()
        H.remove_edge(*e)
        out[e] = hardcore_local(H).e_max - base
    return out


# ---------------------------------------------------------------------------
# 4. LP dual on edge constraints
# ---------------------------------------------------------------------------

def lp_dual(G: nx.Graph) -> dict[tuple[int, int], float] | None:
    """
    Solve  max Σ x_v  s.t.  x_u + x_v ≤ 1 for uv ∈ E,  0 ≤ x_v ≤ 1.
    Return dual variable on each edge constraint (the "shadow price").
    Edges with high dual are the ones that bind in the LP optimum.
    """
    try:
        import cvxpy as cp
    except ImportError:
        return None
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    n = len(nodes)
    x = cp.Variable(n)
    edges = _edges(G)
    edge_cons = []
    for (u, v) in edges:
        edge_cons.append(x[idx[u]] + x[idx[v]] <= 1)
    prob = cp.Problem(cp.Maximize(cp.sum(x)),
                      [x >= 0, x <= 1, *edge_cons])
    prob.solve(solver="SCS", verbose=False)
    if prob.status not in ("optimal", "optimal_inaccurate"):
        return None
    out: dict[tuple[int, int], float] = {}
    for e, c in zip(edges, edge_cons):
        d = c.dual_value
        out[e] = float(abs(d)) if d is not None else 0.0
    return out


# ---------------------------------------------------------------------------
# 5. Lovász ϑ SDP dual on edge constraints
# ---------------------------------------------------------------------------

def sdp_dual(G: nx.Graph) -> dict[tuple[int, int], float] | None:
    """
    Lovász ϑ:  max ⟨J, X⟩  s.t.  X ⪰ 0, tr X = 1, X_uv = 0 for uv ∈ E.
    Returns absolute Lagrange multiplier on each edge equality.
    """
    try:
        import cvxpy as cp
    except ImportError:
        return None
    A = nx.to_numpy_array(G, dtype=np.uint8)
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    n = A.shape[0]
    X = cp.Variable((n, n), symmetric=True)
    cons = [X >> 0, cp.trace(X) == 1]
    edges = _edges(G)
    edge_cons = []
    for (u, v) in edges:
        c = (X[idx[u], idx[v]] == 0)
        edge_cons.append(c)
        cons.append(c)
    prob = cp.Problem(cp.Maximize(cp.sum(X)), cons)
    prob.solve(solver="SCS", verbose=False)
    if prob.status not in ("optimal", "optimal_inaccurate"):
        return None
    out: dict[tuple[int, int], float] = {}
    for e, c in zip(edges, edge_cons):
        d = c.dual_value
        out[e] = float(abs(d)) if d is not None else 0.0
    return out


# ---------------------------------------------------------------------------
# 6. Hoffman gradient (regular graphs only)
# ---------------------------------------------------------------------------

def hoffman_grad(G: nx.Graph) -> dict[tuple[int, int], float] | None:
    """
    For d-regular G, H = N(-λ_min)/(d - λ_min). Hellmann–Feynman:
        ∂λ_min / ∂A_uv  =  2 · w[u] · w[v]
    where w is the unit eigenvector for λ_min. Then
        ∂H / ∂A_uv  =  ∂H/∂λ_min · 2 w[u] w[v]
    with ∂H/∂λ_min = -N · d / (d - λ_min)².

    A *positive* gradient ⇒ adding the edge would *increase* H ⇒
    weakens the bound. We return |∂H/∂A_uv| so high values mean
    "this edge matters most to the spectral bound."
    """
    A = nx.to_numpy_array(G, dtype=float)
    deg = A.sum(axis=1)
    if not np.allclose(deg, deg[0]):
        return None
    d = float(deg[0])
    n = A.shape[0]
    w_all, V = np.linalg.eigh(A)
    lam_min = w_all[0]
    # Detect λ_min multiplicity > 1: simple Hellmann–Feynman is then
    # basis-dependent (degenerate perturbation theory required). Return
    # None so the caller knows the gradient isn't well-defined; we still
    # report H itself separately via utils.alpha_bounds.hoffman_bound.
    if abs(w_all[1] - lam_min) < 1e-6:
        return None
    w = V[:, 0]
    denom = d - lam_min
    if denom <= 0:
        return None
    dH_dlam = -n * d / (denom ** 2)
    out: dict[tuple[int, int], float] = {}
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}
    for (u, v) in _edges(G):
        i, j = idx[u], idx[v]
        dlam = 2.0 * w[i] * w[j]
        out[(u, v)] = float(abs(dH_dlam * dlam))
    return out


METHODS = {
    "drop_alpha":   drop_alpha,
    "drop_e_max":   drop_e_max,
    "drop_l_hc":    drop_l_hc,
    "lp_dual":      lp_dual,
    "sdp_dual":     sdp_dual,
    "hoffman_grad": hoffman_grad,
}
