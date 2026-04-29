"""
experiments/a_critical_bias/penalties.py
=========================================
Cheap structural surrogate for "graph G is far from α-critical" plus an
optional exact #non-α-critical-edges counter.

Three structural correlates, all O(N²) from adj alone:

  s_min_deg(G)  = #{v : deg(v) < 3}
                  basic α-critical ⇒ no degree-2 vertex (subdivision-free).
  s_twin(G)     = #{(u<v) : N[u] = N[v]}
                  basic α-critical ⇒ no twin pair (duplication-free).
  s_hajnal(G)   = #{v : deg(v) > N − 2·α_lb(G) + 1}
                  Hajnal: α-critical ⇒ deg(v) ≤ N − 2·α + 1 for every v.

The combined surrogate is

  pen(G) = w_min · s_min_deg + w_twin · s_twin + w_hajnal · s_hajnal

with default weights (1, 1, 1). All three vanish on basic α-critical
graphs that are Hajnal-saturated; the surrogate being zero is necessary
but not sufficient for α-criticality.

The exact penalty (`exact_non_critical_edges`) uses `alpha_lb` to count
edges e with α_lb(G\\e) ≤ α_lb(G) — a lower bound on #non-critical-edges
(if α_lb misses, edges look critical that aren't). It is O(|E|) α_lb
calls per state, which is too expensive for per-candidate scoring. Use
it only for post-run audits or rare diagnostic snapshots.
"""

from __future__ import annotations

import numpy as np

from utils.alpha_surrogate import alpha_lb


def s_min_deg(adj: np.ndarray, *, threshold: int = 3) -> int:
    """Count vertices with degree below `threshold`. Basic α-critical
    has min-deg ≥ 3."""
    if adj.size == 0:
        return 0
    deg = adj.sum(axis=1)
    return int((deg < threshold).sum())


def s_twin(adj: np.ndarray) -> int:
    """Count unordered vertex pairs (u,v) with identical closed
    neighborhoods (N[u] = N[v]). Basic α-critical = duplication-free
    = twin-free."""
    n = adj.shape[0]
    if n < 2:
        return 0
    # closed adjacency: A_v ∪ {v}
    closed = adj.copy()
    np.fill_diagonal(closed, 1)
    count = 0
    for u in range(n - 1):
        row_u = closed[u]
        for v in range(u + 1, n):
            if np.array_equal(row_u, closed[v]):
                count += 1
    return count


def s_hajnal(
    adj: np.ndarray,
    *,
    alpha: int | None = None,
    rng: np.random.Generator | None = None,
    lb_restarts: int = 4,
) -> int:
    """Count vertices violating Hajnal's degree cap deg(v) > N − 2α + 1.

    Uses the cheap α_lb if `alpha` is not supplied. Lower α makes the cap
    laxer, so using the LB is conservative (under-counts violations);
    that's fine for a surrogate — false negatives are tolerable.
    """
    n = adj.shape[0]
    if n == 0:
        return 0
    if alpha is None:
        alpha = alpha_lb(adj, restarts=lb_restarts, rng=rng)
    deg = adj.sum(axis=1)
    cap = n - 2 * alpha + 1
    return int((deg > cap).sum())


def surrogate_penalty(
    adj: np.ndarray,
    *,
    w_min_deg: float = 1.0,
    w_twin: float = 1.0,
    w_hajnal: float = 1.0,
    alpha: int | None = None,
    rng: np.random.Generator | None = None,
) -> float:
    """Combined structural penalty. Higher = farther from α-critical.

    `alpha` is reused for the Hajnal term if supplied (saves an α_lb
    call when caller has it). Pass `w_hajnal=0` to skip the Hajnal
    component entirely (skips α_lb).
    """
    p = 0.0
    if w_min_deg:
        p += w_min_deg * s_min_deg(adj)
    if w_twin:
        p += w_twin * s_twin(adj)
    if w_hajnal:
        p += w_hajnal * s_hajnal(adj, alpha=alpha, rng=rng)
    return p


def surrogate_components(adj: np.ndarray, alpha: int | None = None,
                         rng: np.random.Generator | None = None) -> dict:
    """Return individual surrogate counts for logging."""
    return {
        "n_min_deg":  s_min_deg(adj),
        "n_twin":     s_twin(adj),
        "n_hajnal":   s_hajnal(adj, alpha=alpha, rng=rng),
    }


# ---------------------------------------------------------------------------
# Exact penalty (slow — for audits, not for per-candidate scoring)
# ---------------------------------------------------------------------------


def exact_non_critical_edges(
    adj: np.ndarray,
    *,
    alpha: int | None = None,
    rng: np.random.Generator | None = None,
    lb_restarts: int = 16,
) -> int:
    """Count edges e with α_lb(G\\e) ≤ α_lb(G).

    True α-criticality of e: α(G\\e) > α(G). Using α_lb on both sides
    means we flag an edge as α-critical only if the LB rises after
    removal — conservative (under-counts criticality, over-counts
    non-criticality). Useful for post-run audits where false positives
    on "non-critical" are tolerable.
    """
    n = adj.shape[0]
    if n == 0:
        return 0
    if rng is None:
        rng = np.random.default_rng()
    if alpha is None:
        alpha = alpha_lb(adj, restarts=lb_restarts, rng=rng)
    edges = list(zip(*np.where(np.triu(adj, k=1))))
    work = adj.copy()
    non_crit = 0
    for u, v in edges:
        work[u, v] = work[v, u] = 0
        a_minus = alpha_lb(work, restarts=lb_restarts, rng=rng)
        if a_minus <= alpha:
            non_crit += 1
        work[u, v] = work[v, u] = 1
    return non_crit
