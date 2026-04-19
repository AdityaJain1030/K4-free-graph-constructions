"""
search/regularity.py
======================
Degree-balancing greedy K4-free construction.

Ported from the `method3` baseline in
`funsearch/experiments/baselines/run_baselines.py`. At each step, pick
the candidate edge that minimizes post-add degree variance among pairs
of low-degree (within +1 of the current min) vertices, subject to a
degree cap and K4-freeness. No α awareness — the heuristic is purely
structural.
"""

import os
import sys

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import is_k4_free

from .base import Search


_DEFAULT_CAPS = (3, 4, 5, 6, 8, 10, 12, 15, 20)


def _default_cap_sweep(n: int) -> list[int]:
    cap = min(20, max(3, n // 2))
    return [d for d in _DEFAULT_CAPS if d <= cap and d <= n - 1]


class RegularitySearch(Search):
    """
    Greedy edge addition driven by degree-variance minimization.

    Constraints
    -----------
    d_max : int | None
        Soft (cap, not target). If set, every construction uses this as
        the per-vertex degree cap. If None, sweep a default list of caps
        and return one candidate per cap; base picks the top_k by c_log.

    Hard vs soft
    ------------
    d_max         : soft  — acts as a per-vertex cap, not an equality.
    K4-freeness   : hard  — rejected mid-construction via `is_k4_free`.
    """

    name = "regularity"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d_max: int | None = None,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            d_max=d_max,
            **kwargs,
        )

    def _build_one(self, d_cap: int) -> np.ndarray:
        n = self.n
        adj = np.zeros((n, n), dtype=np.uint8)
        degs = np.zeros(n, dtype=np.int64)

        while True:
            below_cap = [v for v in range(n) if degs[v] < d_cap]
            if len(below_cap) < 2:
                break
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
                break
            u, v = best_uv
            adj[u, v] = adj[v, u] = 1
            degs[u] += 1
            degs[v] += 1

        return adj

    def _run(self) -> list[nx.Graph]:
        caps = [self.d_max] if self.d_max is not None else _default_cap_sweep(self.n)

        out: list[nx.Graph] = []
        for d_cap in caps:
            adj = self._build_one(d_cap)
            if adj.sum() == 0:
                continue
            G = nx.from_numpy_array(adj)
            self._stamp(G)
            G.graph["metadata"] = {"d_cap": int(d_cap)}
            out.append(G)

        self._log("attempt", level=1, n_caps=len(caps), n_candidates=len(out))
        return out
