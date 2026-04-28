"""
search/algebraic_explicit/norm_graph.py
========================================
Projective-norm Cayley graph on F_{q²}^* with the norm-1 subgroup.

For a prime q, the multiplicative group F_{q²}^* is cyclic of order
q² − 1. The norm map N: F_{q²}^* → F_q^*, N(x) = x^{q+1}, has kernel
K = {x ∈ F_{q²}^* : x^{q+1} = 1} — a cyclic subgroup of order q + 1.

Picking a cyclic generator ω of F_{q²}^* and identifying F_{q²}^* ≅
Z_{q²-1} via ω^i ↔ i, the kernel K corresponds to the subgroup
{(q-1)·k mod (q²-1) : k = 0, …, q}. This search builds the Cayley
graph on Z_{q²-1} with that connection set.

The result is an algebraically-distinguished circulant on n = q² − 1
vertices. For small q this overlaps what `CirculantSearch` would find
by brute force; for q ≥ 7 (n ≥ 48) exhaustive circulant enumeration
is out of reach and this principled selector is the cheap algebraic
pick.

Restricted to **prime q** — q = p^e with e > 1 would need a GF(q)
embedding and is skipped. Prime q alone gives N ∈ {3, 8, 24, 48, 120,
168, 288, 360, …}.
"""

import os
import sys
from math import isqrt

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.graph_props import is_k4_free_nx
from utils.primes import is_prime as _is_prime

from ..base import Search


def _q_from_n(n: int) -> int | None:
    """Solve q² − 1 = n for prime q. Returns q or None."""
    q2 = n + 1
    s = isqrt(q2)
    if s * s != q2:
        return None
    return s if _is_prime(s) else None


def _norm_kernel_conn_set(q: int) -> list[int]:
    """
    Connection set for Cayley on Z_{q²-1} = image of norm-kernel in the
    cyclic group. Symmetric (closed under negation) because −1 sits in
    the kernel for every q ≥ 2.
    """
    n = q * q - 1
    base = q - 1
    S = set()
    for k in range(1, q + 1):
        j = (base * k) % n
        if j == 0:
            continue
        S.add(j)
        S.add((-j) % n)  # enforce symmetry
    return sorted(S)


class NormGraphSearch(Search):
    """
    Cay(Z_{q²−1}, K) with K = norm-kernel. Only runs when n = q² − 1 for
    a prime q.

    Constraints
    -----------
    (none beyond n). q is derived from n.
    """

    name = "norm_graph"

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
        q = _q_from_n(self.n)
        if q is None:
            self._log("skip", level=1,
                      reason="n != q^2 - 1 for any prime q")
            return []

        S = _norm_kernel_conn_set(q)
        if not S:
            self._log("skip", level=1, reason="empty connection set")
            return []

        G = nx.Graph()
        G.add_nodes_from(range(self.n))
        for i in range(self.n):
            for j in S:
                G.add_edge(i, (i + j) % self.n)

        self._stamp(G)
        G.graph["metadata"] = {
            "q": int(q),
            "connection_set": S,
            "construction": "norm_kernel_cayley",
        }
        k4_free = is_k4_free_nx(G)
        self._log("built", level=1, q=q, n=self.n,
                  m=G.number_of_edges(), is_k4_free=int(k4_free))
        return [G]
