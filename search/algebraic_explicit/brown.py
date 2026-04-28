"""
search/algebraic_explicit/brown.py
===================================
Brown's C4-free graph on F_q^3 (so K4-free).

Brown 1966 construction: vertices are the affine 3-space F_q^3
(|V| = q^3) and two distinct points (x, y, z), (x', y', z') are
adjacent iff

    (x - x')^2 + (y - y')^2 + (z - z')^2 = 1   (mod q)

for odd prime q. The construction is C4-free — any two vertices
have at most two common neighbours by Brown's counting argument on
the intersection of two spheres in affine 3-space. C4-free implies
K4-free because K4 contains C4 as a subgraph.

Odd prime q only: the construction uses a fixed non-zero constant
on the right-hand side and relies on enough solutions existing — q
small enough (q = 3) the fixed constant 1 yields a graph with not
enough edges, and we skip; q = 5 is the first interesting case.

Eligible N: q^3 for q ∈ {5, 7, 11, 13} → N ∈ {125, 343, 1331, 2197}.
"""

import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.graph_props import is_k4_free_nx
from utils.primes import is_prime as _is_prime

from ..base import Search


def _q_from_n(n: int) -> int | None:
    """Solve q³ = n for odd prime q ≥ 5."""
    q = round(n ** (1 / 3))
    for cand in (q - 1, q, q + 1):
        if cand >= 5 and _is_prime(cand) and cand ** 3 == n:
            return cand
    return None


def _brown_graph(q: int, rhs: int = 1) -> nx.Graph:
    """
    Build the Brown unit-sphere graph on F_q^3 with fixed right-hand
    side `rhs` ∈ F_q^*. Uses a precomputed set of "sphere offsets"
    (Δ = (dx, dy, dz) with dx² + dy² + dz² = rhs mod q) and connects
    each vertex to v + Δ. This is O(|S| · q³) instead of the naive
    O(q^6).
    """
    # Precompute sphere offsets.
    offsets = []
    for dx in range(q):
        for dy in range(q):
            for dz in range(q):
                if (dx * dx + dy * dy + dz * dz) % q == rhs % q:
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    offsets.append((dx, dy, dz))

    n = q ** 3
    # Vertex indexing: (x, y, z) → x*q² + y*q + z.
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for x in range(q):
        for y in range(q):
            for z in range(q):
                u = x * q * q + y * q + z
                for dx, dy, dz in offsets:
                    xp = (x + dx) % q
                    yp = (y + dy) % q
                    zp = (z + dz) % q
                    v = xp * q * q + yp * q + zp
                    if u < v:
                        G.add_edge(u, v)
    return G


class BrownSearch(Search):
    """
    Brown's C4-free graph on F_q³. Only runs when n = q³ for odd prime
    q ≥ 5.

    Constraints
    -----------
    rhs : int
        Soft. Non-zero right-hand side of the sphere equation. Defaults
        to 1. Any non-zero residue gives an isomorphic construction up
        to field automorphism — exposed for completeness.
    """

    name = "brown"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        rhs: int = 1,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            rhs=rhs,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        q = _q_from_n(self.n)
        if q is None:
            self._log("skip", level=1,
                      reason="n != q^3 for any odd prime q >= 5")
            return []
        if self.rhs % q == 0:
            self._log("skip", level=1, reason="rhs must be non-zero mod q")
            return []

        G = _brown_graph(q, self.rhs)
        self._stamp(G)
        G.graph["metadata"] = {
            "q": int(q),
            "rhs": int(self.rhs % q),
            "construction": "brown_unit_sphere_F_q_3",
        }
        k4_free = is_k4_free_nx(G)
        self._log("built", level=1, q=q, n=G.number_of_nodes(),
                  m=G.number_of_edges(), is_k4_free=int(k4_free))
        return [G]
