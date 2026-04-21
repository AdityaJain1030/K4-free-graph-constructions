"""
utils/alpha_surrogate.py
=========================
Cheap α bounds for use inside a tabu / SA inner loop where calling
the exact solver on every candidate is infeasible.

Two primitives:

  * `alpha_lb`  — random-restart greedy MIS. Returns a value ≤ α(G).
  * `alpha_ub`  — greedy clique cover. Returns a value ≥ α(G) because
                  θ(G) ≥ α(G) for any clique cover θ.

`alpha_surrogate(adj, ...)` returns a dataclass with both bounds and
a best-guess point estimate. When lb == ub the surrogate is exact.

Design principle: these are **ranking signals** for tabu, not
certified values. Final candidates must be re-evaluated with exact α
(graph_props.alpha_bb_clique_cover or alpha_cpsat).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import log

import numpy as np


@dataclass(frozen=True)
class AlphaBracket:
    lb: int
    ub: int
    n: int

    @property
    def is_tight(self) -> bool:
        return self.lb == self.ub

    @property
    def point_estimate(self) -> int:
        # For minimising c = α·d/(N·lnd), a lower-bound α gives an
        # optimistic (smaller) c. Use lb as the point estimate so that
        # ranking-by-c is ranking-by-lb (plus d-penalty).
        return self.lb


# ---------------------------------------------------------------------------
# Lower bound: random greedy MIS
# ---------------------------------------------------------------------------


def _build_nbr_mask(adj: np.ndarray) -> list[int]:
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        row = adj[i]
        for j in range(n):
            if row[j]:
                nbr[i] |= 1 << j
    return nbr


def alpha_lb(
    adj: np.ndarray,
    *,
    restarts: int = 32,
    rng: np.random.Generator | None = None,
    min_degree_first: bool = True,
) -> int:
    """
    Random greedy MIS with restarts. Always returns a *lower bound*
    on α(G).

    `min_degree_first` biases the first candidate to start from the
    lowest-degree vertex — a cheap heuristic that gives better greedy
    solutions on sparse graphs than a uniform start. The remaining
    restarts are uniform-random orderings.
    """
    n = adj.shape[0]
    if n == 0:
        return 0
    nbr = _build_nbr_mask(adj)
    deg = adj.sum(axis=1).astype(np.int64)

    if rng is None:
        rng = np.random.default_rng()

    def greedy(order: list[int]) -> int:
        avail = (1 << n) - 1
        size = 0
        for v in order:
            if avail >> v & 1:
                size += 1
                avail &= ~nbr[v] & ~(1 << v)
        return size

    best = 0
    verts = list(range(n))

    if min_degree_first and restarts > 0:
        deg_order = sorted(verts, key=lambda v: int(deg[v]))
        best = max(best, greedy(deg_order))

    for _ in range(restarts):
        rng.shuffle(verts)
        best = max(best, greedy(verts))
    return best


# ---------------------------------------------------------------------------
# Upper bound: greedy clique cover
# ---------------------------------------------------------------------------


def alpha_ub(adj: np.ndarray, *, rng: np.random.Generator | None = None) -> int:
    """
    Greedy clique partition. Always returns an *upper bound* on α(G)
    because for any clique cover θ ≥ α. Randomised ordering; one pass.

    This is strictly cheaper than the B&B clique-cover in
    graph_props.alpha_bb_clique_cover; the B&B uses this same bound
    inside its search tree.
    """
    n = adj.shape[0]
    if n == 0:
        return 0
    nbr = _build_nbr_mask(adj)
    if rng is None:
        rng = np.random.default_rng()

    order = np.arange(n)
    rng.shuffle(order)
    order_rank = np.empty(n, dtype=np.int64)
    for rank, v in enumerate(order):
        order_rank[v] = rank

    remaining = (1 << n) - 1
    cliques = 0
    while remaining:
        # pick lowest-rank vertex still in `remaining`
        best_v = -1
        best_rank = n + 1
        tmp = remaining
        while tmp:
            v = (tmp & -tmp).bit_length() - 1
            tmp &= tmp - 1
            if order_rank[v] < best_rank:
                best_rank = order_rank[v]
                best_v = v
        cliques += 1
        clique_mask = 1 << best_v
        extendable = remaining & nbr[best_v]
        while extendable:
            w = (extendable & -extendable).bit_length() - 1
            clique_mask |= 1 << w
            extendable &= nbr[w]
            extendable &= ~(1 << w)
        remaining &= ~clique_mask
    return cliques


# ---------------------------------------------------------------------------
# Bracketed surrogate
# ---------------------------------------------------------------------------


def alpha_surrogate(
    adj: np.ndarray,
    *,
    lb_restarts: int = 32,
    rng: np.random.Generator | None = None,
) -> AlphaBracket:
    """
    Compute both bounds in one call. If the greedy clique cover ever
    matches the greedy MIS the result is exact α.
    """
    n = adj.shape[0]
    if n == 0:
        return AlphaBracket(lb=0, ub=0, n=0)
    if rng is None:
        rng = np.random.default_rng()
    lb = alpha_lb(adj, restarts=lb_restarts, rng=rng)
    ub = alpha_ub(adj, rng=rng)
    # Sanity: lb can't exceed ub.
    if lb > ub:
        ub = lb
    return AlphaBracket(lb=lb, ub=ub, n=n)


# ---------------------------------------------------------------------------
# Surrogate c_log
# ---------------------------------------------------------------------------


def c_log_surrogate(
    adj: np.ndarray,
    *,
    lb_restarts: int = 32,
    rng: np.random.Generator | None = None,
    pessimistic: bool = False,
) -> float:
    """
    Compute the surrogate c = α·d_max / (N·ln d_max) using the lower
    bound (default — optimistic) or upper bound (pessimistic=True).

    Returns +inf if n == 0 or d_max ≤ 1 (c undefined).
    """
    n = adj.shape[0]
    if n == 0:
        return float("inf")
    deg = adj.sum(axis=1)
    d_max = int(deg.max())
    if d_max <= 1:
        return float("inf")
    bracket = alpha_surrogate(adj, lb_restarts=lb_restarts, rng=rng)
    a = bracket.ub if pessimistic else bracket.lb
    return a * d_max / (n * log(d_max))
