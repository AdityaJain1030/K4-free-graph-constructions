"""
search/algebraic_explicit/psl_involutions.py
=============================================
Cay(PSL(2, q), trace-0 involutions).

PSL(2, q) has order `q(q² − 1) / gcd(2, q − 1)`. The connection set
is the conjugacy class of involutions (elements of order 2 in the
quotient by ±I); for q odd these are exactly the trace-0 elements of
SL(2, q), and for q even (where −I = I) they are the SL(2,q) elements
satisfying `a + d = 0` and `M ≠ I` modulo the same condition.

Group machinery and field arithmetic come from `utils.algebra.psl2`
and `utils.algebra.field`. No hand-rolled F_q duplication.
"""

import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.algebra import field, prime_power, psl2

from ..base import Search


def _psl_involutions_cayley(q: int) -> nx.Graph:
    """Build Cay(PSL(2, q), trace-0 involutions) as a simple graph on |PSL(2,q)| vertices."""
    fam = psl2(q)
    fq = field(q)
    elements = list(fam.elements)
    idx = fam.elem_index
    identity = fam.identity

    # Connection set: trace-0 elements of PSL, excluding identity.
    S = []
    for M in elements:
        (a, b), (c, d) = M
        if fq.add(a, d) == fq.zero and M != identity:
            S.append(M)

    G = nx.Graph()
    G.add_nodes_from(range(fam.order))
    for g in elements:
        i = idx[g]
        for s in S:
            h = fam.op(g, s)
            j = idx[h]
            if i < j:
                G.add_edge(i, j)
    return G


class PSLInvolutionsSearch(Search):
    """
    Build Cay(PSL(2, q), trace-0 involutions). Caller must pass `q` and
    a matching `n = |PSL(2, q)|`.
    """

    name = "special_cayley"

    def __init__(
        self,
        n: int,
        *,
        q: int,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        **kwargs,
    ):
        super().__init__(
            n,
            q=q,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        if prime_power(self.q) is None:
            self._log("skip", level=1, reason=f"q={self.q} is not a prime power")
            return []
        try:
            fam = psl2(self.q)
        except NotImplementedError as e:
            self._log("skip", level=1, reason=str(e))
            return []

        if self.n != fam.order:
            self._log("skip", level=1,
                      reason=f"|PSL(2,{self.q})|={fam.order}, got n={self.n}")
            return []

        G = _psl_involutions_cayley(self.q)
        self._stamp(G)
        G.graph["metadata"] = {
            "family": "PSL",
            "name": f"Cay(PSL(2,{self.q}), involutions)",
            "group": f"PSL(2,{self.q})",
            "connection_set": "trace0_involutions",
            "q": int(self.q),
        }
        self._log("built", level=1, n=G.number_of_nodes(), m=G.number_of_edges())
        return [G]
