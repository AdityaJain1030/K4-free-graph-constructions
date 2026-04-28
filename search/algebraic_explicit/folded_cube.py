"""
search/algebraic_explicit/folded_cube.py
=========================================
Folded (d+1)-cube as `Cay(Z_2^d, {e_1, …, e_d, (1,…,1)})`.

  * n = 2^d
  * (d+1)-regular
  * Bipartite iff d is odd
  * K₄-free for all d ≥ 3 (every triangle would require three connection
    elements summing to 0 in Z_2^d; for d ≥ 3 no such triple exists in
    `{e_1, …, e_d, (1,…,1)}`)

Named instances:
  * d = 3 → K_{4,4}
  * d = 4 → Clebsch graph
  * d = 5 → folded 6-cube (32 vertices, 6-regular)
  * d ≥ 6 → unnamed; well-studied as distance-regular graphs.
"""

import os
import sys
from itertools import product

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..base import Search


def _folded_cube(d: int) -> nx.Graph:
    elements = [tuple(v) for v in product(range(2), repeat=d)]
    idx = {e: i for i, e in enumerate(elements)}
    S = [tuple(1 if i == k else 0 for i in range(d)) for k in range(d)]
    S.append(tuple(1 for _ in range(d)))
    G = nx.Graph()
    G.add_nodes_from(range(len(elements)))
    for g in elements:
        i = idx[g]
        for s in S:
            h = tuple((g[k] + s[k]) % 2 for k in range(d))
            j = idx[h]
            if i < j:
                G.add_edge(i, j)
    return G


class FoldedCubeSearch(Search):
    """
    Build the folded (d+1)-cube. Caller passes `d` and a matching `n = 2^d`.

    Specializations:
      * d = 3 reproduces K_{4,4}
      * d = 4 reproduces the Clebsch graph
    """

    name = "special_cayley"

    def __init__(
        self,
        n: int,
        *,
        d: int,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        **kwargs,
    ):
        super().__init__(
            n,
            d=d,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        if self.d < 2:
            self._log("skip", level=1, reason=f"d={self.d} requires d >= 2")
            return []
        natural_n = 2 ** self.d
        if self.n != natural_n:
            self._log("skip", level=1,
                      reason=f"folded {self.d+1}-cube is n={natural_n}")
            return []
        G = _folded_cube(self.d)
        self._stamp(G)
        G.graph["metadata"] = {
            "family": "FoldedCube",
            "name": f"Folded {self.d+1}-cube (Z_2^{self.d})",
            "group": f"Z_2^{self.d}",
            "connection_set": "{e_1,...,e_d,(1,...,1)}",
            "d": int(self.d),
        }
        self._log("built", level=1, n=G.number_of_nodes(), m=G.number_of_edges())
        return [G]
