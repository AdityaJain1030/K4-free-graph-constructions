"""
search/algebraic_explicit/a5_double_transpositions.py
======================================================
Cay(A_5, {all 15 double-transpositions}).

A_5 has 60 elements; the 15 double-transpositions (products of two
disjoint 2-cycles) form a conjugacy class closed under inversion (each
double-transposition is its own inverse). 15-regular.
"""

import os
import sys
from itertools import permutations

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..base import Search


_NATURAL_N = 60


def _perm_mul(p, q):
    return tuple(p[q[i]] for i in range(len(p)))


def _parity(p):
    n = len(p)
    inv = 0
    for i in range(n):
        for j in range(i + 1, n):
            if p[i] > p[j]:
                inv += 1
    return inv % 2


def _is_double_transposition(p):
    n = len(p)
    if _parity(p) != 0:
        return False
    fixed = sum(1 for i in range(n) if p[i] == i)
    if fixed != n - 4:
        return False
    for i in range(n):
        if p[i] != i and p[p[i]] != i:
            return False
    return True


def _a5_double_transpositions() -> nx.Graph:
    A5 = [p for p in permutations(range(5)) if _parity(p) == 0]
    idx = {p: i for i, p in enumerate(A5)}
    S = [p for p in A5 if _is_double_transposition(p)]
    G = nx.Graph()
    G.add_nodes_from(range(len(A5)))
    for g in A5:
        i = idx[g]
        for s in S:
            h = _perm_mul(g, s)
            j = idx[h]
            if i < j:
                G.add_edge(i, j)
    return G


class A5DoubleTranspositionsSearch(Search):
    """
    Build Cay(A_5, double-transpositions) (n = 60). No-op if `n != 60`.
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
            self._log("skip", level=1,
                      reason=f"A_5 double-transpositions is only n={_NATURAL_N}")
            return []
        G = _a5_double_transpositions()
        self._stamp(G)
        G.graph["metadata"] = {
            "family": "Simple",
            "name": "Cay(A_5, double-transpositions)",
            "group": "A_5",
            "connection_set": "all_15_double_transpositions",
        }
        self._log("built", level=1, n=G.number_of_nodes(), m=G.number_of_edges())
        return [G]
