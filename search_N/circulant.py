"""
search_N/circulant.py
=====================
Exhaustive K4-free circulant graph search on n vertices (n ≤ 35).

A circulant graph C(n, S) has edges {i, (i±j) mod n} for every j in the
connection set S ⊆ {1, ..., n//2}.  This module enumerates ALL such sets
and returns the top_k graphs by c_log = alpha * d_max / (n * ln(d_max)).
"""

import math
import sys
import os
from itertools import combinations
from typing import NamedTuple

import networkx as nx
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import is_k4_free, alpha_exact, alpha_approx

from .base import Search

MAX_N = 35
_EXACT_ALPHA_THRESHOLD = 100


# ---------------------------------------------------------------------------
# Circulant-specific helpers
# ---------------------------------------------------------------------------

def _circulant_adj(n: int, conn: tuple[int, ...]) -> np.ndarray:
    adj = np.zeros((n, n), dtype=np.uint8)
    for i in range(n):
        for j in conn:
            adj[i, (i + j) % n] = 1
            adj[(i + j) % n, i] = 1
            adj[i, (i - j) % n] = 1
            adj[(i - j) % n, i] = 1
    return adj


def _compute_alpha(adj: np.ndarray, n: int, d: int) -> int:
    if n <= _EXACT_ALPHA_THRESHOLD:
        return alpha_exact(adj)[0]
    approx = alpha_approx(adj)
    # Re-verify exactly if the score looks promising
    if d > 1 and approx * d / (n * math.log(d)) < 1.0:
        return alpha_exact(adj)[0]
    return approx


def _circulant_nx(n: int, conn: tuple[int, ...]) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in conn:
            G.add_edge(i, (i + j) % n)
            G.add_edge(i, (i - j) % n)
    return G


# ---------------------------------------------------------------------------
# Core search routine
# ---------------------------------------------------------------------------

class _Result(NamedTuple):
    c_log: float
    alpha: int
    d: int
    connection_set: tuple[int, ...]
    G: nx.Graph


def _search(n: int, top_k: int, log_fn=None) -> list[_Result]:
    """Enumerate all C(n, S), return top_k by c_log."""
    possible = list(range(1, n // 2 + 1))
    results: list[_Result] = []
    n_checked = 0
    n_k4_free = 0

    for size in range(1, len(possible) + 1):
        for conn in combinations(possible, size):
            n_checked += 1
            adj = _circulant_adj(n, conn)
            d = int(adj[0].sum())
            if d <= 1:
                continue
            if not is_k4_free(adj):
                continue
            n_k4_free += 1
            alpha_val = _compute_alpha(adj, n, d)
            if alpha_val == 0:
                continue
            c = alpha_val * d / (n * math.log(d))
            results.append(_Result(c, alpha_val, d, conn, _circulant_nx(n, conn)))

    if log_fn:
        log_fn("attempt", n_checked=n_checked, n_k4_free=n_k4_free)

    results.sort(key=lambda r: r.c_log)
    return results[:top_k]


# ---------------------------------------------------------------------------
# Search class
# ---------------------------------------------------------------------------

class CirculantSearch(Search):
    """
    Exhaustive K4-free circulant graph search on n vertices (n ≤ 35).

    Attributes
    ----------
    top_k : int   Number of results to return (default 1).

    Class methods
    -------------
    top_k_circulants(n, k) — return top-k results without saving to graph_db.
    """

    name = "circulant"
    multi_result = True
    MAX_N = MAX_N

    def __init__(self, n: int, top_k: int = 1, **kwargs):
        super().__init__(n, **kwargs)
        self.top_k = top_k

    def _run(self) -> list[nx.Graph]:
        if self.n > MAX_N:
            self._log("error", exc=f"n={self.n} exceeds CirculantSearch limit ({MAX_N})")
            return []

        found = _search(self.n, self.top_k, log_fn=self._log)

        if found:
            best = found[0]
            self._log(
                "new_best",
                c_log=round(best.c_log, 6),
                alpha=best.alpha,
                d=best.d,
                connection_set=list(best.connection_set),
                elapsed_s=self._elapsed(),
            )

        for r in found:
            r.G.graph["connection_set"] = list(r.connection_set)
            r.G.graph["alpha"] = r.alpha
            r.G.graph["d"] = r.d
            r.G.graph["c_log"] = round(r.c_log, 6)

        return [r.G for r in found]

    @classmethod
    def top_k_circulants(cls, n: int, k: int = 10) -> list[dict]:
        """
        Return the top-k K4-free circulants on n vertices by c_log, without
        saving to graph_db.  Each entry: {c_log, alpha, d, connection_set, G}.
        """
        return [
            {
                "c_log": r.c_log,
                "alpha": r.alpha,
                "d": r.d,
                "connection_set": r.connection_set,
                "G": r.G,
            }
            for r in _search(n, k)
        ]
