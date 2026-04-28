"""
search/algebraic_explicit/polarity.py
======================================
Erdős–Rényi polarity graph ER(q).

For a prime power q, the projective plane PG(2, q) has q² + q + 1
points. Fix a non-degenerate symmetric bilinear form (the identity
form x·y = x₀y₀ + x₁y₁ + x₂y₂). Two points p, p' are adjacent iff
p · p' = 0 in F_q and p ≠ p'.

ER(q) is C₄-free (so also K₄-free), (q+1)-regular on all but the
q+1 *absolute points* (points with p·p = 0, which would be self-
loops and get removed — they end up with degree q).

Handles every prime power q for which `utils.algebra.field` can build
F_q. The eligible-N → q solver and the construction itself are field-
agnostic; field arithmetic flows through the `field(q)` interface.

Call `PolaritySearch(n=N)` with any N; it derives q from N via
q² + q + 1 = N and skips if N is not of that form with q a prime power.
"""

import os
import sys
from math import isqrt

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.graph_props import is_k4_free_nx
from utils.algebra import field, prime_power

from ..base import Search


def _q_from_n(n: int) -> int | None:
    """Solve q² + q + 1 = n for positive integer q. Returns None if no integer solution."""
    # q = (-1 + sqrt(4n - 3)) / 2
    disc = 4 * n - 3
    if disc < 0:
        return None
    s = isqrt(disc)
    if s * s != disc:
        return None
    num = s - 1
    if num <= 0 or num % 2 != 0:
        return None
    return num // 2


def _pg2_points(F):
    """Canonical projective-2-plane point reps over F_q (first non-zero coord = 1)."""
    pts: list[tuple] = [(F.zero, F.zero, F.one)]
    for c in F.elements:
        pts.append((F.zero, F.one, c))
    for b in F.elements:
        for c in F.elements:
            pts.append((F.one, b, c))
    return pts


def _polarity_graph(q: int) -> nx.Graph:
    F = field(q)
    pts = _pg2_points(F)
    G = nx.Graph()
    G.add_nodes_from(range(len(pts)))
    for i in range(len(pts)):
        pi = pts[i]
        for j in range(i + 1, len(pts)):
            pj = pts[j]
            dot = F.add(F.add(F.mul(pi[0], pj[0]), F.mul(pi[1], pj[1])), F.mul(pi[2], pj[2]))
            if dot == F.zero:
                G.add_edge(i, j)
    return G


class PolaritySearch(Search):
    """
    Build the Erdős–Rényi polarity graph ER(q) for the unique prime power q
    satisfying q² + q + 1 = n. No-op if n is not of that form with q a
    prime power supported by `utils.algebra.field`.

    Constraints
    -----------
    (none beyond n) — the graph is determined by q.

    Returns at most one graph. Removes self-loops (absolute points) so
    every returned graph is simple.
    """

    name = "polarity"

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
            self._log("skip", level=1, reason="n != q^2 + q + 1 for any integer q")
            return []
        pe = prime_power(q)
        if pe is None:
            self._log("skip", level=1, reason=f"q={q} is not a prime power")
            return []

        try:
            G = _polarity_graph(q)
        except NotImplementedError as e:
            self._log("skip", level=1, reason=str(e))
            return []
        # Drop any self-loops (absolute points).
        G.remove_edges_from(nx.selfloop_edges(G))
        self._stamp(G)
        p, e = pe
        G.graph["metadata"] = {
            "q": int(q),
            "construction": "erdos_renyi_polarity",
            "q_is_prime_power": e > 1,
        }
        k4_free = is_k4_free_nx(G)
        self._log("built", level=1, q=q, n=G.number_of_nodes(),
                  m=G.number_of_edges(), is_k4_free=int(k4_free))
        return [G]
