"""
search/algebraic_explicit/hamming.py
=====================================
Hamming graph H(d, q) as `Cay(Z_q^d, {±e_i : 1 ≤ i ≤ d})`.

Vertex set Z_q^d (size q^d). Two vertices are adjacent iff they differ
in exactly one coordinate. d(d-1)-regular when q ≥ 3 (degree 2d).

K₄-freeness: each maximal clique sits along a single axis (the q-clique
spanned by varying one coordinate), so H(d, q) is K_q-free for q ≥ 4
and K₄-free precisely when q ≤ 3 (with q=3 giving K_3-saturated maximal
cliques, q=2 the d-cube which is bipartite).
"""

import os
import sys
from itertools import product

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..base import Search


def _hamming(d: int, q: int) -> nx.Graph:
    elements = [tuple(v) for v in product(range(q), repeat=d)]
    idx = {e: i for i, e in enumerate(elements)}
    # Connection set: ±e_i for each axis, with +e_i = (0,...,1,...,0)
    S = []
    for i in range(d):
        for k in range(1, q):
            s = tuple(k if j == i else 0 for j in range(d))
            S.append(s)
    G = nx.Graph()
    G.add_nodes_from(range(len(elements)))
    for g in elements:
        i = idx[g]
        for s in S:
            h = tuple((g[k] + s[k]) % q for k in range(d))
            j = idx[h]
            if i < j:
                G.add_edge(i, j)
    return G


class HammingSearch(Search):
    """
    Build H(d, q) = Cay(Z_q^d, {±e_i}). Defaults to H(3, 3) (n = 27).
    No-op unless `n == q ** d`.
    """

    name = "special_cayley"

    def __init__(
        self,
        n: int,
        *,
        d: int = 3,
        q: int = 3,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        **kwargs,
    ):
        super().__init__(
            n,
            d=d,
            q=q,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        natural_n = self.q ** self.d
        if self.n != natural_n:
            self._log("skip", level=1,
                      reason=f"H({self.d},{self.q}) is n={natural_n}")
            return []
        G = _hamming(self.d, self.q)
        self._stamp(G)
        G.graph["metadata"] = {
            "family": "Hamming",
            "name": f"H({self.d},{self.q}) (Z_{self.q}^{self.d})",
            "group": f"Z_{self.q}^{self.d}",
            "connection_set": "{±e_i}",
            "d": int(self.d),
            "q": int(self.q),
        }
        self._log("built", level=1, n=G.number_of_nodes(), m=G.number_of_edges())
        return [G]
