"""
search/cayley_tabu.py
======================
Tabu search over Cayley-graph connection sets.

For each group Γ of order n in `families_of_order(n)`, the search runs
Tabu (Parczyk Algorithm 2) over the indicator vector of inversion
orbits of Γ \\ {e}. Each bit toggles one orbit in/out of the connection
set S, and the state vector has length |inversion_orbits(Γ)| ≈ (n-1)/2.

Cost function during search is a **surrogate**:

    cost(bits) = +inf                            if Cay(Γ, S) has a K₄
               = +inf                            if d_max ≤ 1
               = α_lb · d_max / (n · ln d_max)   otherwise

where α_lb is random-restart greedy MIS (`alpha_surrogate.alpha_lb`).
α_lb ≤ α(G), so the surrogate is a *lower* bound on the true c; search
ranks graphs by this lower bound then the base class re-evaluates the
top-k with exact α.

Why lower-bound as signal: graphs with small true α tend to have
small α_lb; the ordering is approximately right, and restarts within
α_lb smooth out variance. Also, for vertex-transitive graphs — which
is what we're searching — α_lb is often exact when a greedy restart
happens to start from a vertex in a MIS, so the signal is sharp.
"""

from __future__ import annotations

import os
import sys
import time
from typing import Hashable

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.graph_props import is_k4_free, alpha_bb_clique_cover, c_log_value
from utils.alpha_surrogate import alpha_lb

from ..base import Search
from .tabu import multi_restart_tabu, TabuResult
from utils.algebra import (
    GroupSpec,
    families_of_order,
    cayley_adj_from_bitvec,
    connection_set_from_bitvec,
)


def _adj_to_nx(adj: np.ndarray) -> nx.Graph:
    n = adj.shape[0]
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                G.add_edge(i, j)
    return G


def _make_cost_fn(G: GroupSpec, rng: np.random.Generator, lb_restarts: int):
    """Return a cost callable suitable for tabu. Closes over G, rng."""
    from math import log

    n = G.order

    def cost(bits: np.ndarray) -> float:
        # Empty S → empty graph, d_max = 0.
        if not bits.any():
            return float("inf")
        adj = cayley_adj_from_bitvec(G, bits)
        deg = adj.sum(axis=1)
        d_max = int(deg.max())
        if d_max <= 1:
            return float("inf")
        if not is_k4_free(adj):
            return float("inf")
        a_lb = alpha_lb(adj, restarts=lb_restarts, rng=rng)
        return a_lb * d_max / (n * log(d_max))

    return cost


class CayleyTabuSearch(Search):
    """
    Run Tabu on every supported group of order n, keep top_k by c_log.

    Constraints
    -----------
    n_iters : int
        Soft. Tabu iterations per restart. Default 300.
    n_restarts : int
        Soft. Tabu restarts per group. Default 3.
    tabu_len : int | None
        Soft. Length of the modified-bits tabu list. Default = L//4.
    lb_restarts : int
        Soft. α-surrogate greedy-MIS restarts during cost eval. Default 24.
    time_limit_s : float | None
        Soft. Wall-clock cap per group. Default None (no cap).
    groups : list[str] | None
        Soft. Restrict search to group names in this list. Default: all.
    """

    name = "cayley_tabu"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        n_iters: int = 300,
        n_restarts: int = 3,
        tabu_len: int | None = None,
        lb_restarts: int = 24,
        time_limit_s: float | None = None,
        groups: list[str] | None = None,
        random_seed: int | None = None,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            n_iters=n_iters,
            n_restarts=n_restarts,
            tabu_len=tabu_len,
            lb_restarts=lb_restarts,
            time_limit_s=time_limit_s,
            groups=tuple(groups) if groups else None,
            random_seed=random_seed,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        rng = np.random.default_rng(self.random_seed)
        fams = families_of_order(self.n)
        if self.groups:
            fams = [f for f in fams if f.name in set(self.groups)]
        if not fams:
            self._log("skip", level=1, reason="no supported group of this order")
            return []

        out: list[nx.Graph] = []
        for fam in fams:
            L = fam.n_orbits
            if L == 0:
                continue
            cost_fn = _make_cost_fn(fam, rng, self.lb_restarts)
            t0 = time.monotonic()
            res: TabuResult = multi_restart_tabu(
                L=L,
                cost=cost_fn,
                n_restarts=self.n_restarts,
                n_iters=self.n_iters,
                tabu_len=self.tabu_len,
                rng=rng,
                time_limit_s=self.time_limit_s,
            )
            elapsed = time.monotonic() - t0

            self._log(
                "group_done",
                level=1,
                group=fam.name,
                L=L,
                best_surrogate_cost=_fmt_inf(res.best_cost),
                best_iter=res.best_iter,
                n_iters=res.n_iters,
                elapsed_s=round(elapsed, 3),
            )

            if not np.isfinite(res.best_cost):
                continue

            adj = cayley_adj_from_bitvec(fam, res.best_state)
            if not is_k4_free(adj):
                # cost fn should prevent this, but be defensive
                continue

            G = _adj_to_nx(adj)
            self._stamp(G)
            conn = connection_set_from_bitvec(fam, res.best_state)
            # Convert tuple/ints to json-safe
            conn_serialisable = [list(s) if isinstance(s, tuple) else s for s in conn]
            G.graph["metadata"] = {
                "group": fam.name,
                "connection_set": conn_serialisable,
                "surrogate_c_log": float(res.best_cost),
                "tabu_n_iters": int(res.n_iters),
                "tabu_best_iter": int(res.best_iter),
            }
            out.append(G)
        return out

    def _alpha_of(self, G: nx.Graph):
        """
        Override: Cayley graphs are vertex-transitive, so α can be computed
        via the exact B&B clique-cover solver (fast on sparse K4-free)
        without needing the SAT hammer. This is the "verification" step.
        """
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_bb_clique_cover(adj)


def _fmt_inf(x: float) -> float | str:
    if not np.isfinite(x):
        return "inf"
    return round(float(x), 6)
