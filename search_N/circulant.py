"""
search_N/circulant.py
=====================
K4-free circulant graph enumeration on n vertices.

A circulant C(n, S) has edges {i, (i±j) mod n} for each j ∈ S,
S ⊆ {1, ..., n//2}. Every circulant is vertex-transitive and regular
(degree 2|S|, or 2|S|-1 when n is even and n/2 ∈ S).

This search enumerates all connection sets (optionally restricted to
|S| == connection_set_size) and hands the K4-free survivors to the
base class, which scores and keeps the top_k by c_log.
"""

import os
import sys
from itertools import combinations

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import is_k4_free_nx

from .base import Search


def _circulant(n: int, conn: tuple[int, ...]) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in conn:
            G.add_edge(i, (i + j) % n)
            G.add_edge(i, (i - j) % n)
    return G


class CirculantSearch(Search):
    """
    Enumerate every K4-free circulant on n vertices, keep top_k by c_log.

    Constraints
    -----------
    connection_set_size : int | None
        Hard. If given, only enumerate connection sets S with |S| == this.
        If None (default), enumerate every non-empty S ⊆ {1, ..., n//2}.
    """

    name = "circulant"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        connection_set_size: int | None = None,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            connection_set_size=connection_set_size,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        jumps = list(range(1, self.n // 2 + 1))
        sizes = (
            [self.connection_set_size]
            if self.connection_set_size is not None
            else range(1, len(jumps) + 1)
        )

        out: list[nx.Graph] = []
        n_checked = 0
        n_k4_free = 0
        for size in sizes:
            for conn in combinations(jumps, size):
                n_checked += 1
                G = _circulant(self.n, conn)
                if not is_k4_free_nx(G):
                    continue
                n_k4_free += 1
                self._stamp(G)
                G.graph["metadata"] = {"connection_set": list(conn)}
                out.append(G)

        self._log("attempt", level=1, n_checked=n_checked, n_k4_free=n_k4_free)
        return out
