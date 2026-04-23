"""
search/groups_psl.py
=====================
PSL(2, q) as a `GroupSpec`, so the existing Cayley-tabu machinery
(inversion_orbits → bitvec → tabu) works unchanged.

`psl2(q)` builds the group for q ∈ {prime, prime-power}. Elements are
canonical 2x2 matrices over F_q with determinant 1, taken modulo
{±I}. F_q arithmetic is built inline (prime field or F_8 explicit
polynomial representation) — no sympy/galois dependency.

Why: SmallGroups cap skips orders > 500 in the GAP path, and PSL(2, q)
for q ∈ {8, 11, 13, 16, ...} all live above that threshold. The
Hoffman analysis identified those as the only remaining route to a new
λ_min profile.
"""

from __future__ import annotations

from itertools import product
from typing import Callable

from .groups import GroupSpec


# ---------------------------------------------------------------------------
# F_q arithmetic
# ---------------------------------------------------------------------------


class _FieldPrime:
    """F_p for p prime. Elements are ints in [0, p)."""
    def __init__(self, p: int):
        self.q = p
        self.zero = 0
        self.one = 1
        self.elements = list(range(p))

    def add(self, a, b): return (a + b) % self.q
    def sub(self, a, b): return (a - b) % self.q
    def mul(self, a, b): return (a * b) % self.q
    def neg(self, a):    return (-a) % self.q

    def inv(self, a):
        if a == 0:
            raise ZeroDivisionError
        return pow(a, self.q - 2, self.q)


class _FieldF8:
    """F_8 = F_2[x] / (x^3 + x + 1). Elements are 3-bit ints 0..7 (bits = coeffs a + bx + cx^2)."""
    def __init__(self):
        self.q = 8
        self.zero = 0
        self.one = 1
        self.elements = list(range(8))
        self._inv_table = self._build_inv_table()

    @staticmethod
    def add(a, b): return a ^ b  # XOR in char 2
    sub = add
    def neg(self, a): return a  # char 2

    @staticmethod
    def mul(a, b):
        # polynomial multiplication mod (x^3 + x + 1) i.e. x^3 = x + 1
        r = 0
        for i in range(3):
            if (b >> i) & 1:
                r ^= a << i
        # reduce bits 3..5
        for i in range(5, 2, -1):
            if (r >> i) & 1:
                # x^i = x^{i-3} * (x+1) = x^{i-2} + x^{i-3}  (since x^3 = x + 1)
                r ^= (1 << i) | (1 << (i - 2)) | (1 << (i - 3))
        return r & 0b111

    def _build_inv_table(self):
        t = {}
        for a in range(1, 8):
            for b in range(1, 8):
                if self.mul(a, b) == 1:
                    t[a] = b
                    break
        return t

    def inv(self, a):
        if a == 0:
            raise ZeroDivisionError
        return self._inv_table[a]


def _field(q: int):
    if q == 8:
        return _FieldF8()
    # check prime
    if q < 2:
        raise ValueError(f"q={q} not valid")
    for d in range(2, int(q ** 0.5) + 1):
        if q % d == 0:
            raise NotImplementedError(
                f"q={q} is a non-trivial prime power other than 8; extend _field()"
            )
    return _FieldPrime(q)


# ---------------------------------------------------------------------------
# PSL(2, q)
# ---------------------------------------------------------------------------


def _mat_mul(A, B, fq):
    (a, b), (c, d) = A
    (e, f), (g, h) = B
    return (
        (fq.add(fq.mul(a, e), fq.mul(b, g)), fq.add(fq.mul(a, f), fq.mul(b, h))),
        (fq.add(fq.mul(c, e), fq.mul(d, g)), fq.add(fq.mul(c, f), fq.mul(d, h))),
    )


def _mat_neg(A, fq):
    (a, b), (c, d) = A
    return ((fq.neg(a), fq.neg(b)), (fq.neg(c), fq.neg(d)))


def _mat_inv(A, fq):
    # For det=1 matrices: inv((a,b;c,d)) = (d,-b;-c,a)
    (a, b), (c, d) = A
    return ((d, fq.neg(b)), (fq.neg(c), a))


def _canonical_psl(A, fq):
    """Representative of {A, -A}, chosen as lex-min."""
    negA = _mat_neg(A, fq)
    return min(A, negA)


def _enumerate_sl2(fq):
    """All 2x2 matrices over F_q with det 1."""
    for a in fq.elements:
        for b in fq.elements:
            for c in fq.elements:
                # d is determined by det: ad - bc = 1 → d = (1 + bc)/a if a != 0
                if a != fq.zero:
                    ainv = fq.inv(a)
                    d = fq.mul(ainv, fq.add(fq.one, fq.mul(b, c)))
                    yield ((a, b), (c, d))
                else:
                    # a = 0 → -bc = 1 → c = -b^{-1}, d free
                    if b == fq.zero:
                        continue
                    binv = fq.inv(b)
                    c_required = fq.neg(binv)
                    if c != c_required:
                        continue
                    for d in fq.elements:
                        yield ((a, b), (c, d))


def psl2(q: int) -> GroupSpec:
    """Build PSL(2, q) as a GroupSpec."""
    fq = _field(q)

    # Enumerate PSL elements (canonical reps)
    seen = set()
    elements = []
    char_even = (q % 2 == 0)
    for M in _enumerate_sl2(fq):
        if char_even:
            if M in seen:
                continue
            seen.add(M)
            elements.append(M)
        else:
            C = _canonical_psl(M, fq)
            if C in seen:
                continue
            seen.add(C)
            elements.append(C)

    identity = ((fq.one, fq.zero), (fq.zero, fq.one))
    # for char_even, identity is trivially (1,0;0,1) which is fixed by enumeration
    # for char_odd, canonical of I is min(I, -I); make sure identity reflects that
    if not char_even:
        identity = _canonical_psl(identity, fq)

    elem_index = {e: i for i, e in enumerate(elements)}

    def op(X, Y):
        P = _mat_mul(X, Y, fq)
        if char_even:
            return P
        return _canonical_psl(P, fq)

    def inv_of(X):
        I = _mat_inv(X, fq)
        if char_even:
            return I
        return _canonical_psl(I, fq)

    inverse_of = {e: inv_of(e) for e in elements}

    return GroupSpec(
        name=f"PSL(2,{q})",
        order=len(elements),
        elements=elements,
        identity=identity,
        inverse_of=inverse_of,
        op=op,
        elem_index=elem_index,
    )
