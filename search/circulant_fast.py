"""
search/circulant_fast.py
========================
Scalable K4-free circulant search for large n.

CirculantSearch enumerates every S ⊆ {1, ..., n//2} via
itertools.combinations, which blows up past n ≈ 35. This class caps
|S|, walks the K4-free sub-lattice with a DFS that prunes any extension
that creates a K4, deduplicates under the multiplier action of Z_n*
(C(n, S) ≅ C(n, u·S) for u coprime to n), and prunes candidates whose
greedy-α lower bound on c already exceeds the current top_k-th best.
Designed to hit n up to ~100 with max_conn_size around 8.

Exact α via `utils.graph_props.alpha_cpsat(..., vertex_transitive=True)`.
The x[0]=1 pin is sound because circulants are vertex-transitive, and it
collapses the MIS search by n — on low-|S| circulants (cycles, |S|=2)
the generic clique-cover B&B takes seconds per graph while CP-SAT stays
in the 10–100 ms range. The greedy pre-filter is essential: CP-SAT
carries ~100 ms of solver-init overhead per call, so we can't afford to
run it on every DFS survivor.

Not exhaustive over the full circulant lattice — "the best K4-free
circulant with |S| ≤ max_conn_size, up to multiplier isomorphism".
For the best optima in practice this is a tight bound: every known
optimum in the existing catalog has |S| ≤ 4.
"""

import os
import sys
from math import gcd

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import alpha_approx, alpha_cpsat, c_log_value

from .base import Search


# ── circulant primitives ─────────────────────────────────────────────────────


def _fold(x: int, n: int) -> int:
    """Map x ∈ Z_n to its representative in {0, 1, ..., n//2}."""
    x = x % n
    return x if x + x <= n else n - x


def _full_from_half(S_half: tuple[int, ...], n: int) -> frozenset[int]:
    """Symmetrize S_half to the full connection set S ∪ -S in Z_n."""
    out: set[int] = set()
    for s in S_half:
        out.add(s)
        out.add((n - s) % n)
    return frozenset(out)


def _d_max(S_half: tuple[int, ...], n: int) -> int:
    """Max degree of C(n, S_half). 2|S|, minus 1 when n is even and n/2 ∈ S."""
    d = 2 * len(S_half)
    if n % 2 == 0 and (n // 2) in S_half:
        d -= 1
    return d


def _has_k4(S_full: frozenset[int], n: int) -> bool:
    """
    K4 in C(n, S_full) ⟺ triangle in the "difference graph" on S_full
    (edges (a, b) with a-b ∈ S_full). O(|S_full|^3) with early-exit.
    """
    S_sorted = sorted(S_full)
    L = len(S_sorted)
    if L < 3:
        return False
    for i in range(L):
        a = S_sorted[i]
        for j in range(i + 1, L):
            b = S_sorted[j]
            if (b - a) % n not in S_full:
                continue
            for k in range(j + 1, L):
                c = S_sorted[k]
                if (c - a) % n in S_full and (c - b) % n in S_full:
                    return True
    return False


def _circulant_adj(n: int, S_full: frozenset[int]) -> np.ndarray:
    adj = np.zeros((n, n), dtype=np.uint8)
    S_arr = np.fromiter(S_full, dtype=np.int64, count=len(S_full))
    for i in range(n):
        adj[i, (i + S_arr) % n] = 1
    return adj


def _circulant_graph(n: int, S_full: frozenset[int]) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for s in S_full:
            G.add_edge(i, (i + s) % n)
    return G


def _canonical_half(S_half: tuple[int, ...], n: int, units: list[int]) -> tuple[int, ...]:
    """Lex-smallest image of S_half under the multiplier action of Z_n*."""
    best = S_half
    for u in units:
        img = tuple(sorted(_fold(u * s, n) for s in S_half))
        if img < best:
            best = img
    return best


# ── search class ─────────────────────────────────────────────────────────────


class CirculantSearchFast(Search):
    """
    Large-n K4-free circulant search. Caps |S|, prunes K4 extensions
    during DFS, dedupes by Z_n* multiplier action, and filters survivors
    by a greedy-α lower bound on c before exact α.

    Constraints
    -----------
    max_conn_size : int
        Hard. Upper bound on |S|. Default 8.
    min_conn_size : int
        Hard. Lower bound on |S|. Default 1.
    """

    name = "circulant_fast"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        max_conn_size: int = 8,
        min_conn_size: int = 1,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            max_conn_size=max_conn_size,
            min_conn_size=min_conn_size,
            **kwargs,
        )

    def _alpha_of(self, G: nx.Graph) -> tuple[int, list[int]]:
        # Circulants are vertex-transitive, so CP-SAT with x[0]=1 stays
        # sound and is much faster than clique-cover B&B on sparse
        # connection sets (|S|≤2) at moderate n.
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_cpsat(adj, vertex_transitive=True)

    def _run(self) -> list[nx.Graph]:
        n = self.n
        if n < 3:
            return []
        half = n // 2
        units = [u for u in range(1, n) if gcd(u, n) == 1]

        # Pass 1: DFS enumerates canonical K4-free connection sets and
        # tags each with a greedy α lower bound (cheap) to rank them by
        # an optimistic c. Pass 2: sorted ascending c_lo, run exact α
        # via CP-SAT with vertex-transitive pin (x[0]=1, sound for
        # circulants) until c_lo crosses the running top-k cutoff.
        #
        # Why CP-SAT not clique-cover B&B: on low-|S| circulants (|S|≤2
        # at n=80) the clique-cover upper bound leaves a huge search
        # tree and solves take seconds; CP-SAT stays in 10–100 ms with
        # the VT pin.
        #
        # Why the greedy pre-filter: CP-SAT costs ~100 ms per call even
        # on tiny instances (solver init), so we cannot afford to run
        # it on every DFS survivor — there are thousands at n≥80. Even
        # a few random restarts of greedy MIS give a lower bound tight
        # enough to prune almost all of them before pass 2.
        candidates: list[tuple[float, tuple[int, ...], frozenset[int]]] = []
        n_nodes = 0
        n_k4_skipped = 0
        n_noncanonical = 0

        def dfs(S_half: tuple[int, ...], S_full: frozenset[int], min_next: int):
            nonlocal n_nodes, n_k4_skipped, n_noncanonical

            k = len(S_half)
            if k >= self.min_conn_size:
                if _canonical_half(S_half, n, units) != S_half:
                    n_noncanonical += 1
                else:
                    d = _d_max(S_half, n)
                    if d >= 2:
                        adj = _circulant_adj(n, S_full)
                        alpha_lo = alpha_approx(adj, restarts=10)
                        c_lo = c_log_value(alpha_lo, n, d)
                        if c_lo is not None:
                            candidates.append((c_lo, S_half, S_full))

            if k >= self.max_conn_size:
                return
            for j in range(min_next, half + 1):
                n_nodes += 1
                new_full = S_full | {j, (n - j) % n}
                if _has_k4(new_full, n):
                    n_k4_skipped += 1
                    continue
                dfs(S_half + (j,), new_full, j + 1)

        dfs((), frozenset(), 1)

        candidates.sort(key=lambda t: t[0])

        collected_c: list[float] = []

        def kth_cutoff() -> float:
            if len(collected_c) >= self.top_k:
                return collected_c[self.top_k - 1]
            return float("inf")

        results: list[nx.Graph] = []
        n_evaluated = 0
        for c_lo, S_half, S_full in candidates:
            if c_lo >= kth_cutoff():
                break
            adj = _circulant_adj(n, S_full)
            alpha_true, _ = alpha_cpsat(adj, vertex_transitive=True)
            d = _d_max(S_half, n)
            c_true = c_log_value(alpha_true, n, d)
            n_evaluated += 1
            if c_true is None:
                continue
            collected_c.append(c_true)
            collected_c.sort()
            if len(collected_c) > self.top_k:
                collected_c.pop()
            G = _circulant_graph(n, S_full)
            self._stamp(G)
            G.graph["metadata"] = {"connection_set": list(S_half)}
            results.append(G)

        self._log(
            "attempt",
            level=1,
            n_dfs_nodes=n_nodes,
            n_k4_skipped=n_k4_skipped,
            n_noncanonical=n_noncanonical,
            n_candidates=len(candidates),
            n_evaluated=n_evaluated,
            n_multiplier_units=len(units),
        )
        return results
