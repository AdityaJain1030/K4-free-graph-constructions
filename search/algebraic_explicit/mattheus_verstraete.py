"""
search/algebraic_explicit/mattheus_verstraete.py
=================================================
Explicit K4-free construction `Hq*` from Mattheus & Verstraete (2024),
"The asymptotics of r(4, t)", arXiv:2306.04007.

Vertices are the secants to the Hermitian unital in PG(2, q²). Two secants
are adjacent in Hq iff they meet at a unital point. Hq is a union of q³+1
maximal cliques (pencils, one per unital point; each of size q², pairwise
sharing ≤ 1 vertex). Hq itself is NOT K4-free, but every copy of K4 has
≥ 3 vertices in some pencil (Prop 2.iv of the paper).

Hq* replaces each pencil's clique by a random complete bipartite graph
(Bernoulli-½ vertex partition per pencil). The result is K4-free: the
three would-be K4 vertices in a pencil now lie in a bipartite induced
subgraph, so they can't form a triangle, so no K4 survives.

V1 restricts to PRIME q ∈ {2, 3, 5, 7} → n ∈ {12, 63, 525, 2107}. Prime
powers with k > 1 (q = 4, 8, 9, ...) would require F_{p^k} extensions
and are not supported yet.

Motivation: this is a **benchmark** from the literature, not a c_log winner.
Back-of-envelope gives c_log(Hq*) ≈ q^{1/3}(log q)^{1/3}/3, which grows
with q. Use it to sanity-check and cite, not to win the objective.
"""

import os
import random as _random
import sys

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from utils.primes import smallest_qnr as _smallest_qnr

from ..base import Search


# ─── valid q / n ────────────────────────────────────────────────────────────

_VALID_PRIME_QS = (2, 3, 5, 7)


def _n_for_q(q: int) -> int:
    return q * q * (q * q - q + 1)


def _q_from_n(n: int) -> int | None:
    """Return the prime q ∈ _VALID_PRIME_QS with q²(q²−q+1) == n, else None."""
    for q in _VALID_PRIME_QS:
        if _n_for_q(q) == n:
            return q
    return None


# ─── F_{q²} arithmetic ──────────────────────────────────────────────────────
#
# Elements are pairs (a, b) representing a + b·α, where α is a root of the
# fixed irreducible polynomial x² + p·x + c over F_q.
#
#   q = 2:   x² + x + 1      (p, c) = (1, 1)
#   q odd:   x² − nonres     (p, c) = (0, (−nonres) mod q)
#
# α² = −p·α − c   ⇒   mul uses: r0 = a·a' − b·b'·c,
#                                r1 = a·b' + b·a' − b·b'·p   (all mod q)


class _Fq2:
    """Tiny F_{q²} arithmetic on (a, b) = a + b·α."""

    __slots__ = ("q", "p_coef", "c_coef", "order")

    def __init__(self, q: int):
        if q == 2:
            self.p_coef, self.c_coef = 1, 1
        else:
            nonres = _smallest_qnr(q)
            self.p_coef, self.c_coef = 0, (-nonres) % q
        self.q = q
        self.order = q * q  # |F_{q²}|

    # zero / one as (a, b)
    @property
    def zero(self) -> tuple[int, int]:
        return (0, 0)

    @property
    def one(self) -> tuple[int, int]:
        return (1, 0)

    def add(self, u, v):
        q = self.q
        return ((u[0] + v[0]) % q, (u[1] + v[1]) % q)

    def neg(self, u):
        q = self.q
        return ((-u[0]) % q, (-u[1]) % q)

    def sub(self, u, v):
        q = self.q
        return ((u[0] - v[0]) % q, (u[1] - v[1]) % q)

    def mul(self, u, v):
        q = self.q
        a, b = u
        c, d = v
        bd = b * d
        r0 = (a * c - bd * self.c_coef) % q
        r1 = (a * d + b * c - bd * self.p_coef) % q
        return (r0, r1)

    def scalar_mul(self, u, k: int):
        q = self.q
        return ((u[0] * k) % q, (u[1] * k) % q)

    def pow(self, u, k: int):
        r = self.one
        base = u
        while k > 0:
            if k & 1:
                r = self.mul(r, base)
            k >>= 1
            if k:
                base = self.mul(base, base)
        return r

    def inv(self, u):
        if u == self.zero:
            raise ZeroDivisionError("inverse of zero in F_{q²}")
        # u^(q² − 2) via fast exponentiation
        return self.pow(u, self.order - 2)

    def frobenius(self, u):
        """u^q — the nontrivial Galois automorphism of F_{q²} over F_q."""
        return self.pow(u, self.q)

    def norm(self, u) -> int:
        """N(u) = u · u^q ∈ F_q; returned as an int in [0, q)."""
        val = self.mul(u, self.frobenius(u))
        # val is (a, b); for u · u^q the result must lie in F_q, so b == 0.
        # We return a; an assert would be redundant given the construction.
        return val[0]


# ─── PG(2, q²) / unital / secants / pencils ─────────────────────────────────


def _all_fq2_elements(Fq2: _Fq2) -> list[tuple[int, int]]:
    q = Fq2.q
    return [(a, b) for a in range(q) for b in range(q)]


def _canonical_point(triple, Fq2: _Fq2):
    """
    Scale a nonzero (x, y, z) in F_{q²}³ by the inverse of its first nonzero
    coordinate so the canonical rep has that coordinate equal to one.
    """
    for i, comp in enumerate(triple):
        if comp != Fq2.zero:
            inv = Fq2.inv(comp)
            return tuple(Fq2.mul(c, inv) for c in triple)
    raise ValueError("zero vector has no projective representative")


def _projective_points(Fq2: _Fq2) -> list[tuple]:
    """Enumerate all q⁴ + q² + 1 points of PG(2, F_{q²}) as canonical reps."""
    elems = _all_fq2_elements(Fq2)
    zero = Fq2.zero
    seen = set()
    out: list[tuple] = []
    for x in elems:
        for y in elems:
            for z in elems:
                if x == zero and y == zero and z == zero:
                    continue
                rep = _canonical_point((x, y, z), Fq2)
                if rep not in seen:
                    seen.add(rep)
                    out.append(rep)
    return out


def _hermitian_unital(points: list[tuple], Fq2: _Fq2) -> list[int]:
    """Indices into `points` that lie on x^(q+1) + y^(q+1) + z^(q+1) = 0."""
    q = Fq2.q
    out = []
    for idx, (x, y, z) in enumerate(points):
        s = (Fq2.norm(x) + Fq2.norm(y) + Fq2.norm(z)) % q
        if s == 0:
            out.append(idx)
    return out


def _line_through(P, Q, Fq2: _Fq2) -> tuple:
    """Coefficients (a, b, c) of the line through two distinct proj points P, Q.
    Computed as the F_{q²} cross product P × Q."""
    x1, y1, z1 = P
    x2, y2, z2 = Q
    a = Fq2.sub(Fq2.mul(y1, z2), Fq2.mul(z1, y2))
    b = Fq2.sub(Fq2.mul(z1, x2), Fq2.mul(x1, z2))
    c = Fq2.sub(Fq2.mul(x1, y2), Fq2.mul(y1, x2))
    return (a, b, c)


def _canonical_line(line, Fq2: _Fq2) -> tuple:
    """Canonicalize a line (a, b, c) by scaling first nonzero entry to 1."""
    return _canonical_point(line, Fq2)


def _enumerate_secants_and_pencils(
    points: list[tuple],
    unital: list[int],
    Fq2: _Fq2,
) -> tuple[list[frozenset[int]], list[list[int]]]:
    """
    Compute secants and pencils.

    Returns
    -------
    secants : list[frozenset[int]]
        Each secant is the set of unital-point indices it contains. Length
        should be q²(q²−q+1); each entry has exactly q+1 members.
    pencils : list[list[int]]
        Pencils[k] = list of secant indices passing through unital[k]. Each
        should have length q².

    Strategy
    --------
    For every unordered pair (i, j) of unital indices compute the line
    through points[i], points[j]; canonicalize; accumulate unital indices
    by canonical line. Each line collects exactly q+1 unital indices, and
    C(q+1, 2) pairs map to the same line, so the dedup is automatic.
    """
    lines_to_units: dict[tuple, set[int]] = {}
    for a in range(len(unital)):
        ia = unital[a]
        Pa = points[ia]
        for b in range(a + 1, len(unital)):
            ib = unital[b]
            Pb = points[ib]
            line = _line_through(Pa, Pb, Fq2)
            cline = _canonical_line(line, Fq2)
            bucket = lines_to_units.get(cline)
            if bucket is None:
                bucket = set()
                lines_to_units[cline] = bucket
            bucket.add(ia)
            bucket.add(ib)

    secants: list[frozenset[int]] = [frozenset(s) for s in lines_to_units.values()]

    unital_to_idx = {p_idx: k for k, p_idx in enumerate(unital)}
    pencils: list[list[int]] = [[] for _ in unital]
    for s_idx, s in enumerate(secants):
        for p_idx in s:
            pencils[unital_to_idx[p_idx]].append(s_idx)

    return secants, pencils


# ─── the Search subclass ────────────────────────────────────────────────────


class MattheusVerstraeteSearch(Search):
    """
    Random K4-free realization of the Mattheus–Verstraete construction Hq*.

    Constraints
    -----------
    seed : int
        Base RNG seed. Trial t uses ``random.Random(seed*1000 + t)``.
        Same seed + same n + same top_k ⇒ identical edge sets.

    n is hard-constrained: only n ∈ {12, 63, 525, 2107} (prime q = 2, 3, 5, 7)
    are accepted. Any other n raises ValueError on construction.

    Notes
    -----
    - is_k4_free is True by the bipartition argument (paper Prop 2.iv); base
      class verifies this on every returned graph.
    - top_k independent realizations are produced per call; base keeps the
      best by c_log.
    - c_log grows with q — this is a benchmark construction, not a winner.
    """

    name = "mattheus_verstraete"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        seed: int = 0,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            seed=seed,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        q = _q_from_n(self.n)
        if q is None:
            self._log("skip", level=1,
                      reason=f"n != q²(q²−q+1) for any prime q in {_VALID_PRIME_QS}")
            return []
        Fq2 = _Fq2(q)

        points = _projective_points(Fq2)
        unital = _hermitian_unital(points, Fq2)
        secants, pencils = _enumerate_secants_and_pencils(points, unital, Fq2)
        n_sec = len(secants)

        # Structural invariants — cheap, and load-bearing for K4-freeness.
        assert len(unital) == q ** 3 + 1, (len(unital), q ** 3 + 1)
        assert n_sec == q * q * (q * q - q + 1), (n_sec, self.n)
        assert all(len(s) == q + 1 for s in secants)
        assert all(len(P) == q * q for P in pencils)

        self._log(
            "mv_structure",
            level=1,
            n_vertices=n_sec,
            n_pencils=len(pencils),
            pencil_size=q * q,
        )

        out: list[nx.Graph] = []
        for trial in range(self.top_k):
            rng = _random.Random(self.seed * 1000 + trial)
            G = nx.Graph()
            G.add_nodes_from(range(n_sec))
            for P in pencils:
                sides = [rng.random() < 0.5 for _ in P]
                A = [v for v, s in zip(P, sides) if s]
                B = [v for v, s in zip(P, sides) if not s]
                for u in A:
                    for v in B:
                        G.add_edge(u, v)
            self._stamp(G)
            G.graph["metadata"] = {
                "q": q,
                "seed": self.seed,
                "trial": trial,
                "n_pencils": len(pencils),
                "pencil_size": q * q,
            }
            out.append(G)

        return out
