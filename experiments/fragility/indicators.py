"""
experiments/fragility/indicators.py
===================================
Per-seed structural metrics computed once at G_0 and recorded
alongside every fragility run. The point of these is to *correlate*
fragility shape (Test A distribution, Test E basin volume) with
static structural properties of the seed.

The most important indicator is the edge-sensitivity vector

    Δ_e = α(G − e) − α(G)   for every edge e ∈ E(G).

Δ_e ∈ {0, 1, 2, ...}. The α-criticality fraction ρ_c = |{e : Δ_e > 0}| / |E|
is the fraction of edges that are "tight" — α-critical iff ρ_c = 1.

Other indicators (Hoffman saturation, θ slack) are reused from
existing primitives in `utils/alpha_bounds.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import networkx as nx

from utils.alpha_bounds import hoffman_bound, lovasz_theta as _theta
from utils.graph_props import (
    adding_induces_k4,
    alpha_bb_clique_cover,
    c_log_value,
)

from experiments.fragility.move_taxonomy import (
    all_move_kinds,
    move_in_degree,
)


@dataclass
class Indicators:
    """All scalar / small-vector indicators for a single seed graph."""
    n: int
    n_edges: int
    d_max: int
    d_min: int
    d_avg: float
    is_regular: bool
    alpha: int
    c_log: float | None
    edge_sensitivities: list[int]    # one entry per edge, in some fixed order
    rho_c: float                     # |{Δ_e > 0}| / |E|
    hoffman: float | None            # None iff non-regular
    hoffman_sat: float | None        # α / H
    theta: float | None              # cvxpy may be missing → None
    theta_slack: float | None        # θ − α
    move_in_degree: dict[str, int]   # one entry per move kind
    k4_margin: int                   # non-edges whose addition would create K4
    extras: dict = field(default_factory=dict)


def _alpha(adj: np.ndarray) -> int:
    a, _ = alpha_bb_clique_cover(adj)
    return int(a)


def edge_sensitivities(adj: np.ndarray, base_alpha: int | None = None
                       ) -> list[int]:
    """Δ_e for every edge in the same enumeration order as
    `move_taxonomy._edges`.

    Δ_e = α(G − e) − α(G) ≥ 0. Each entry costs one α solve via
    `alpha_bb_clique_cover` (which is what `edge_methods.drop_alpha`
    uses). This is identical in spirit to `drop_alpha` but indexed
    by the enumeration order rather than (u,v) so it lines up with
    `move_taxonomy.enumerate_delete`.
    """
    base = base_alpha if base_alpha is not None else _alpha(adj)
    n = adj.shape[0]
    out: list[int] = []
    for i in range(n):
        for j in range(i + 1, n):
            if not adj[i, j]:
                continue
            sub = adj.copy()
            sub[i, j] = sub[j, i] = 0
            out.append(_alpha(sub) - base)
    return out


def k4_margin(adj: np.ndarray) -> int:
    """Number of non-edges whose addition would create a K4. Non-edges
    that are 'tight' against the K4-free constraint."""
    n = adj.shape[0]
    cnt = 0
    for i in range(n):
        for j in range(i + 1, n):
            if not adj[i, j] and adding_induces_k4(adj, i, j):
                cnt += 1
    return cnt


def compute_indicators(adj: np.ndarray, *,
                       compute_theta: bool = True,
                       compute_sensitivities: bool = True,
                       move_kinds: list[str] | None = None) -> Indicators:
    """One-shot indicator block. Heavy: edge sensitivities cost |E| α
    solves; θ takes one SDP solve. Pass compute_theta=False or
    compute_sensitivities=False to skip the expensive parts when
    only running cheap diagnostics."""
    n = adj.shape[0]
    n_edges = int(adj.sum() // 2)
    deg = adj.sum(axis=1).astype(int)
    d_max = int(deg.max()) if n > 0 else 0
    d_min = int(deg.min()) if n > 0 else 0
    d_avg = float(deg.mean()) if n > 0 else 0.0
    is_regular = bool(np.all(deg == deg[0]))

    alpha = _alpha(adj)
    cl = c_log_value(alpha, n, d_max) if d_max > 1 else None

    if compute_sensitivities:
        sens = edge_sensitivities(adj, base_alpha=alpha)
        rho = sum(1 for s in sens if s > 0) / max(1, len(sens))
    else:
        sens = []
        rho = float("nan")

    G = nx.from_numpy_array(adj)
    if is_regular and d_max >= 1:
        try:
            H = hoffman_bound(G)
        except ValueError:
            H = None
    else:
        H = None
    hsat = (alpha / H) if (H is not None and H > 0) else None

    if compute_theta:
        try:
            th = _theta(G)
        except Exception:
            th = None
    else:
        th = None
    th_slack = (th - alpha) if th is not None else None

    kinds = move_kinds or all_move_kinds()
    in_deg = {k: move_in_degree(adj, k) for k in kinds}

    return Indicators(
        n=n, n_edges=n_edges, d_max=d_max, d_min=d_min, d_avg=d_avg,
        is_regular=is_regular, alpha=alpha, c_log=cl,
        edge_sensitivities=sens, rho_c=rho,
        hoffman=H, hoffman_sat=hsat,
        theta=th, theta_slack=th_slack,
        move_in_degree=in_deg,
        k4_margin=k4_margin(adj),
    )


def indicators_to_dict(ind: Indicators) -> dict:
    """Flatten Indicators to a JSON-serialisable dict (lists, floats, ints).
    The edge-sensitivity vector is kept as a list."""
    d = {
        "n": ind.n,
        "n_edges": ind.n_edges,
        "d_max": ind.d_max,
        "d_min": ind.d_min,
        "d_avg": ind.d_avg,
        "is_regular": ind.is_regular,
        "alpha": ind.alpha,
        "c_log": ind.c_log,
        "edge_sensitivities": ind.edge_sensitivities,
        "rho_c": ind.rho_c,
        "hoffman": ind.hoffman,
        "hoffman_sat": ind.hoffman_sat,
        "theta": ind.theta,
        "theta_slack": ind.theta_slack,
        "move_in_degree": dict(ind.move_in_degree),
        "k4_margin": ind.k4_margin,
    }
    if ind.extras:
        d["extras"] = ind.extras
    return d
