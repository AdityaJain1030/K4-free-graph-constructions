"""
search/cayley_tabu_gap.py
==========================
GAP-backed Cayley tabu search.

Identical to `CayleyTabuSearch` except the family iterator is sourced
from GAP's SmallGroups library (`families_of_order_gap`) instead of
the hand-coded `families_of_order`. This gives every finite group of
order n — including the non-abelians we were previously missing
(Q_8, SL(2,3), Frobenius Z_7⋊Z_3, etc.).

The tabu core, cost function, and scoring path are reused verbatim
from `cayley_tabu.py`; this file contributes only the family source
and a separate `name = "cayley_tabu_gap"` source tag so results land
in their own graph_db bucket.
"""

from __future__ import annotations

import time

import numpy as np
import networkx as nx

from utils.graph_props import is_k4_free

from .cayley_tabu import CayleyTabuSearch, _adj_to_nx, _make_cost_fn, _fmt_inf
from utils.algebra import (
    cayley_adj_from_bitvec,
    connection_set_from_bitvec,
    families_of_order_gap,
)
from .tabu import multi_restart_tabu, TabuResult


class CayleyTabuGapSearch(CayleyTabuSearch):
    """
    GAP-SmallGroups-backed variant of `CayleyTabuSearch`. See the parent
    class for all search knobs — this subclass only swaps the family
    iterator and the source name.
    """

    name = "cayley_tabu_gap"

    def _run(self) -> list[nx.Graph]:
        rng = np.random.default_rng(self.random_seed)
        fams = families_of_order_gap(self.n)
        if self.groups:
            fams = [f for f in fams if f.name in set(self.groups)]
        if not fams:
            self._log("skip", level=1, reason="no SmallGroup of this order")
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
                continue

            G = _adj_to_nx(adj)
            self._stamp(G)
            conn = connection_set_from_bitvec(fam, res.best_state)
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
