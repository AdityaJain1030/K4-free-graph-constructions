"""
search/cayley.py
==================
Cayley graphs on Z_p with k-th power residues as the connection set.

For prime p and integer k ≥ 2 with (p-1) % k == 0, the k-th powers in
Z_p^* form a multiplicative subgroup of order (p-1)/k. Taking that
subgroup as the connection set of a Cayley graph on Z_p gives a
(p-1)/k-regular, arc-transitive graph. Since the subgroup is closed
under multiplication by any k-th power, it partitions Z_p^* into k
cosets and the graph spectrum has exactly k+1 distinct eigenvalues —
the trivial degree, plus k Gauss-period eigenvalues. For k=2, p≡1(4)
this recovers the Paley graph. For k=3, p≡1(6) it gives the cubic
residue Cayley graph (e.g. Cay(Z_19, R_3), the best N=19 K4-free graph
already in the DB, reinterpreted).

Why a separate search instead of a seed in CirculantSearch?
CirculantSearch is exhaustive for n ≤ ~35 so algebraic seeding adds
nothing there. For n > 35 the enumeration is infeasible, and algebraic
families are one of the few principled ways to land a candidate. This
class skips n that are not eligible primes, so it costs ~nothing to
run across an n-sweep alongside the other searches.
"""

import os
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import is_k4_free_nx

from .base import Search


# ── number-theory helpers (stdlib only) ──────────────────────────────────────


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def _prime_factors(n: int) -> list[int]:
    out: list[int] = []
    d = 2
    while d * d <= n:
        if n % d == 0:
            out.append(d)
            while n % d == 0:
                n //= d
        d += 1
    if n > 1:
        out.append(n)
    return out


def _primitive_root(p: int) -> int:
    """Smallest primitive root mod prime p."""
    phi = p - 1
    qs = _prime_factors(phi)
    for g in range(2, p):
        if all(pow(g, phi // q, p) != 1 for q in qs):
            return g
    raise ValueError(f"no primitive root found mod {p}")


def _residue_subgroup(p: int, k: int) -> list[int]:
    """k-th power residues mod prime p (requires (p-1) % k == 0)."""
    g = _primitive_root(p)
    h = pow(g, k, p)
    size = (p - 1) // k
    out: list[int] = []
    x = 1
    for _ in range(size):
        out.append(x)
        x = (x * h) % p
    return sorted(out)


def _cayley_on_zp(p: int, S: list[int]) -> nx.Graph:
    """Cayley graph on Z_p with connection set S (assumed symmetric, S = -S)."""
    G = nx.Graph()
    G.add_nodes_from(range(p))
    for i in range(p):
        for s in S:
            G.add_edge(i, (i + s) % p)
    return G


# ── search class ─────────────────────────────────────────────────────────────


class CayleyResidueSearch(Search):
    """
    Cayley(Z_p, R_k) for prime p with p ≡ 1 (mod 2k), across k in
    `residue_indices`. Eligibility (p prime + p ≡ 1 mod 2k) guarantees
    -1 ∈ R_k, so the connection set is symmetric and the graph is
    undirected. For n not eligible under any requested k, returns [].

    Constraints
    -----------
    residue_indices : tuple[int, ...]
        Hard. Which k to try. Defaults to (2, 3, 6) — Paley, cubic, sextic.
        k=2 requires p ≡ 1 (mod 4); k=3 requires p ≡ 1 (mod 6);
        k=6 requires p ≡ 1 (mod 12). Non-eligible (k, p) are skipped
        silently.
    """

    name = "cayley"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        residue_indices: tuple[int, ...] = (2, 3, 6),
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            residue_indices=tuple(residue_indices),
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        p = self.n
        if not _is_prime(p) or p < 5:
            self._log("skip", level=1, reason="n is not a prime ≥ 5")
            return []

        out: list[nx.Graph] = []
        n_built = 0
        n_k4_free = 0
        for k in self.residue_indices:
            if (p - 1) % (2 * k) != 0:
                continue
            S = _residue_subgroup(p, k)
            G = _cayley_on_zp(p, S)
            n_built += 1
            if not is_k4_free_nx(G):
                continue
            n_k4_free += 1
            self._stamp(G)
            G.graph["metadata"] = {
                "prime": p,
                "residue_index": k,
                "connection_set": S,
            }
            out.append(G)

        self._log(
            "attempt",
            level=1,
            n_built=n_built,
            n_k4_free=n_k4_free,
            residue_indices=list(self.residue_indices),
        )
        return out
