"""
search/algebraic_explicit/shrikhande.py
========================================
The Shrikhande graph as `Cay(Z_4 × Z_4, {±(1,0), ±(0,1), ±(1,1)})`.

16 vertices, 6-regular, srg(16, 6, 2, 2). Cospectral mate of the
4×4 rook graph but not isomorphic to it.
"""

import os
import sys
from itertools import product

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..base import Search


_NATURAL_N = 16


def _shrikhande() -> nx.Graph:
    elements = [tuple(v) for v in product(range(4), repeat=2)]
    idx = {e: i for i, e in enumerate(elements)}
    S = [(1, 0), (3, 0), (0, 1), (0, 3), (1, 1), (3, 3)]
    G = nx.Graph()
    G.add_nodes_from(range(len(elements)))
    for g in elements:
        i = idx[g]
        for s in S:
            h = ((g[0] + s[0]) % 4, (g[1] + s[1]) % 4)
            j = idx[h]
            if i < j:
                G.add_edge(i, j)
    return G


class ShrikhandeSearch(Search):
    """
    Build the Shrikhande graph (n = 16). No-op if `n != 16`.
    """

    name = "special_cayley"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        if self.n != _NATURAL_N:
            self._log("skip", level=1, reason=f"Shrikhande is only n={_NATURAL_N}")
            return []
        G = _shrikhande()
        self._stamp(G)
        G.graph["metadata"] = {
            "family": "SRG",
            "name": "Shrikhande (Z_4xZ_4)",
            "group": "Z_4xZ_4",
            "connection_set": "{±(1,0),±(0,1),±(1,1)}",
        }
        self._log("built", level=1, n=G.number_of_nodes(), m=G.number_of_edges())
        return [G]
