"""
search_N/brute_force.py
=======================
Exhaustive K4-free graph search via nauty geng.

Returns the top_k graphs by c_log across all non-isomorphic K4-free graphs
on n vertices. Cap n to what geng can realistically enumerate.
"""

import os
import sys
import time

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.pynauty import find_geng, graphs_via_geng

from .base import Search


class BruteForce(Search):
    """
    Enumerate every non-isomorphic K4-free graph on n vertices (via geng)
    and return the top_k by c_log.

    Attributes
    ----------
    top_k : int   Number of results to return (default 1).
    """

    name = "brute_force"
    multi_result = True

    def __init__(self, n: int, top_k: int = 1, **kwargs):
        super().__init__(n, **kwargs)
        self.top_k = top_k

    def _run(self) -> list[nx.Graph]:
        geng = find_geng()
        if geng is None:
            self._log("error", exc="geng not found on PATH")
            return []

        start = time.time()
        found: list[tuple[float, float, nx.Graph]] = []   # (c_log, time_to_find, G)
        n_checked = 0
        for G in graphs_via_geng(geng, self.n):
            n_checked += 1
            c = self.c_log(G)
            if c is None:
                continue
            found.append((c, round(time.time() - start, 4), G))

        self._log("attempt", n_checked=n_checked, n_valid=len(found))

        found.sort(key=lambda r: r[0])
        found = found[: self.top_k]

        if found:
            best_c, best_t, _ = found[0]
            self._log("new_best", c_log=round(best_c, 6), time_to_find=best_t)

        for _, t, G in found:
            G.graph["time_to_find"] = t

        return [G for _, _, G in found]
