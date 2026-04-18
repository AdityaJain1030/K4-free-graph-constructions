"""
search_N/brute_force.py
=======================
Exhaustive K4-free graph search via nauty geng (or pure-Python fallback).
Only practical for n ≤ 10.

Returns the top_k graphs (by c_log) found across ALL non-isomorphic K4-free
graphs on n vertices.  With top_k=1 (default) only the best is returned.
"""

import sys
import os

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.pynauty import find_geng, graphs_via_geng, graphs_via_python

from .base import Search

MAX_N = 10  # nauty geng is feasible; beyond this the graph count explodes


class BruteForce(Search):
    """
    Enumerate every non-isomorphic K4-free graph on n vertices and return the
    top_k by c_log.  Requires nauty (geng) for n > 6; falls back to pure Python.

    Attributes
    ----------
    top_k : int   Number of results to return (default 1).
    """

    name = "brute_force"
    multi_result = True
    MAX_N = MAX_N

    def __init__(self, n: int, top_k: int = 1, **kwargs):
        super().__init__(n, **kwargs)
        self.top_k = top_k

    def _run(self) -> list[nx.Graph]:
        if self.n > MAX_N:
            self._log("error", exc=f"n={self.n} exceeds BruteForce limit ({MAX_N})")
            return []

        geng = find_geng()
        backend = "geng" if geng else "python"
        self._log("attempt", backend=backend, n=self.n)

        gen = graphs_via_geng(geng, self.n) if geng else graphs_via_python(self.n)

        scored: list[tuple[float, nx.Graph]] = []
        n_total = 0
        for G in gen:
            n_total += 1
            c = self.c_log(G)
            if c is None:
                continue
            scored.append((c, G))

        scored.sort(key=lambda x: x[0])
        self._log("attempt", n_graphs=n_total, n_valid=len(scored))

        if scored:
            best_c, best_G = scored[0]
            d_max = max(d for _, d in best_G.degree())
            self._log(
                "new_best",
                c_log=round(best_c, 6),
                d_max=d_max,
                elapsed_s=self._elapsed(),
            )

        return [G for _, G in scored[: self.top_k]]
