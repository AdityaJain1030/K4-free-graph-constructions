"""
search/brute_force.py
=======================
Exhaustive K4-free graph enumeration via nauty `geng`.

Streams every non-isomorphic K4-free graph on n vertices and keeps only
the top_k by c_log incrementally — required because at n=10 there are
millions of K4-free graphs and accumulating them blows memory.

Feasible roughly up to n=10; beyond that geng's output is too large
even to stream-score.
"""

import heapq
import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import alpha_nx, c_log_value
from utils.nauty import find_geng, graphs_via_geng

from .base import Search


class BruteForce(Search):
    """
    Enumerate every non-isomorphic K4-free graph on n vertices via geng.

    Constraints (all hard — enforced by the geng flag `-k`):
        - K4-free (guaranteed by the enumerator).

    Memory: bounded by top_k. Each candidate is scored on the fly and
    only the top_k smallest c_log graphs are retained.
    """

    name = "brute_force"

    def _run(self) -> list[nx.Graph]:
        geng = find_geng()
        if geng is None:
            self._log("error", exc="geng not found on PATH")
            return []

        k = max(self.top_k, 1)
        # Bounded max-heap on c_log via negation: heap[0] is the worst
        # (largest c_log) of the k kept; replace it when a smaller arrives.
        heap: list[tuple[float, int, nx.Graph]] = []
        counter = 0
        n_checked = 0

        for G in graphs_via_geng(geng, self.n, flags="-k"):
            n_checked += 1
            self._stamp(G)
            d_max = max((d for _, d in G.degree()), default=0)
            alpha, _ = alpha_nx(G)
            c = c_log_value(alpha, self.n, d_max)
            c_key = float("inf") if c is None else c

            if len(heap) < k:
                heapq.heappush(heap, (-c_key, counter, G))
            elif -heap[0][0] > c_key:
                heapq.heapreplace(heap, (-c_key, counter, G))
            counter += 1

        self._log("attempt", level=1, n_checked=n_checked)
        return [G for _, _, G in sorted(heap, key=lambda x: -x[0])]
