"""
search/brute_force.py
=======================
Exhaustive K4-free graph enumeration via nauty `geng`.

Streams every non-isomorphic K4-free graph on n vertices and hands them
to the base class, which scores and keeps the top_k by c_log.

Feasible roughly up to n=10; beyond that geng's output is too large.
"""

import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.nauty import find_geng, graphs_via_geng

from .base import Search


class BruteForce(Search):
    """
    Enumerate every non-isomorphic K4-free graph on n vertices via geng.

    Constraints (all hard — enforced by the geng flag `-k`):
        - K4-free (guaranteed by the enumerator).
    """

    name = "brute_force"

    def _run(self) -> list[nx.Graph]:
        geng = find_geng()
        if geng is None:
            self._log("error", exc="geng not found on PATH")
            return []

        out: list[nx.Graph] = []
        n_checked = 0
        for G in graphs_via_geng(geng, self.n, flags="-k"):
            n_checked += 1
            self._stamp(G)
            out.append(G)

        self._log("attempt", level=1, n_checked=n_checked)
        return out
