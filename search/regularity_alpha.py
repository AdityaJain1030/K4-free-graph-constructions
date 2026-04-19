"""
search/regularity_alpha.py
==========================
α-aware variant of `RegularitySearch`.

Ported from the `method3b` baseline in
`funsearch/experiments/baselines/run_baselines.py`. Same degree-variance
greedy as `RegularitySearch` until α stagnates — every 10 edges the
true α is computed; if it has not dropped in 20 edges the search takes
one step by the "most-common-neighbors" heuristic (the pair whose
adjacency has the biggest overlap, subject to the cap and K4-freeness)
and then returns to degree balancing.
"""

import os
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import alpha_exact, is_k4_free

from .base import Search


_DEFAULT_CAPS = (3, 4, 5, 6, 8, 10, 12, 15, 20)


def _default_cap_sweep(n: int) -> list[int]:
    cap = min(20, max(3, n // 2))
    return [d for d in _DEFAULT_CAPS if d <= cap and d <= n - 1]


class RegularityAlphaSearch(Search):
    """
    Degree-balancing greedy with α-driven strategy switch.

    Behavior
    --------
    At each step try to add an edge between two low-degree below-cap
    vertices minimizing the post-add degree variance (same as
    `RegularitySearch`). Every `alpha_check_every` edges compute α
    exactly. If α has not dropped in `alpha_patience` edges, take one
    step picking the pair with the most common neighbors (still subject
    to d_cap and K4-freeness), then resume degree balancing.

    Constraints
    -----------
    d_max : int | None
        Soft (cap, not target). If set, every construction uses this as
        the per-vertex degree cap. If None, sweep a default list of caps
        and return one candidate per cap; base picks the top_k by c_log.
    alpha_check_every : int, default 10
        Edges between exact α evaluations.
    alpha_patience : int, default 20
        Edges without an α drop before the common-neighbor intervention.

    Hard vs soft
    ------------
    d_max             : soft  — per-vertex cap.
    K4-freeness       : hard  — rejected mid-construction via `is_k4_free`.
    alpha_check_every : soft  — tuning knob, not a constraint.
    alpha_patience    : soft  — tuning knob, not a constraint.
    """

    name = "regularity_alpha"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d_max: int | None = None,
        alpha_check_every: int = 10,
        alpha_patience: int = 20,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            d_max=d_max,
            alpha_check_every=alpha_check_every,
            alpha_patience=alpha_patience,
            **kwargs,
        )

    # ─────────────────────────────────────────────────────────────────
    # Strategies: each tries to add one edge, returns True on success.
    # ─────────────────────────────────────────────────────────────────

    def _add_by_regularity(self, adj: np.ndarray, degs: np.ndarray,
                           d_cap: int) -> bool:
        n = self.n
        below_cap = [v for v in range(n) if degs[v] < d_cap]
        if len(below_cap) < 2:
            return False
        min_deg = min(degs[v] for v in below_cap)
        low_verts = [v for v in below_cap if degs[v] <= min_deg + 1]
        if len(low_verts) < 2:
            low_verts = below_cap

        best_var = float("inf")
        best_uv: tuple[int, int] | None = None
        for i in range(len(low_verts)):
            u = low_verts[i]
            for j in range(i + 1, len(low_verts)):
                v = low_verts[j]
                if adj[u, v]:
                    continue
                adj[u, v] = adj[v, u] = 1
                if is_k4_free(adj):
                    degs[u] += 1
                    degs[v] += 1
                    var_new = float(np.var(degs))
                    degs[u] -= 1
                    degs[v] -= 1
                    if var_new < best_var:
                        best_var = var_new
                        best_uv = (u, v)
                adj[u, v] = adj[v, u] = 0

        if best_uv is None:
            return False
        u, v = best_uv
        adj[u, v] = adj[v, u] = 1
        degs[u] += 1
        degs[v] += 1
        return True

    def _add_by_common_nbr(self, adj: np.ndarray, degs: np.ndarray,
                           d_cap: int) -> bool:
        n = self.n
        best_cn = -1
        best_uv: tuple[int, int] | None = None
        for u in range(n):
            if degs[u] >= d_cap:
                continue
            for v in range(u + 1, n):
                if adj[u, v] or degs[v] >= d_cap:
                    continue
                adj[u, v] = adj[v, u] = 1
                k4_ok = is_k4_free(adj)
                adj[u, v] = adj[v, u] = 0
                if not k4_ok:
                    continue
                cn = int(np.dot(adj[u], adj[v]))
                if cn > best_cn:
                    best_cn = cn
                    best_uv = (u, v)
        if best_uv is None:
            return False
        u, v = best_uv
        adj[u, v] = adj[v, u] = 1
        degs[u] += 1
        degs[v] += 1
        return True

    # ─────────────────────────────────────────────────────────────────
    # Per-cap construction
    # ─────────────────────────────────────────────────────────────────

    def _build_one(self, d_cap: int) -> tuple[np.ndarray, dict]:
        n = self.n
        adj = np.zeros((n, n), dtype=np.uint8)
        degs = np.zeros(n, dtype=np.int64)

        last_alpha: int | None = None
        edges_since_alpha_drop = 0
        common_nbr_fires = 0
        alpha_drops = 0
        step = 0
        safety_cap = n * d_cap + 10

        while step < safety_cap:
            # Periodic α check
            if step > 0 and step % self.alpha_check_every == 0:
                if int(degs.max()) >= 2:
                    a, _ = alpha_exact(adj)
                    if last_alpha is not None and a < last_alpha:
                        edges_since_alpha_drop = 0
                        alpha_drops += 1
                    else:
                        edges_since_alpha_drop += self.alpha_check_every
                    last_alpha = a

            use_common_nbr = edges_since_alpha_drop >= self.alpha_patience
            if use_common_nbr:
                added = (self._add_by_common_nbr(adj, degs, d_cap)
                         or self._add_by_regularity(adj, degs, d_cap))
                edges_since_alpha_drop = 0
                common_nbr_fires += 1
            else:
                added = self._add_by_regularity(adj, degs, d_cap)

            if not added:
                break
            step += 1

        meta = {
            "d_cap": int(d_cap),
            "edges_added": step,
            "common_nbr_fires": common_nbr_fires,
            "alpha_drops": alpha_drops,
        }
        return adj, meta

    def _run(self) -> list[nx.Graph]:
        caps = [self.d_max] if self.d_max is not None else _default_cap_sweep(self.n)

        out: list[nx.Graph] = []
        for d_cap in caps:
            adj, meta = self._build_one(d_cap)
            if adj.sum() == 0:
                continue
            G = nx.from_numpy_array(adj)
            self._stamp(G)
            G.graph["metadata"] = meta
            out.append(G)

        self._log("attempt", level=1, n_caps=len(caps), n_candidates=len(out))
        return out
