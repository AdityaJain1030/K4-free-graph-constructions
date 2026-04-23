"""
search/_fq.py
==============
Minimal F_q arithmetic for prime powers used by polarity / unitary
constructions. Hand-coded irreducibles keep us off `galois`/sympy.

Elements are ints 0..q-1; addition/multiplication go through the
field object. `enumerate_nonzero()` and `is_zero(x)` are the only
primitives the polarity code needs beyond add/mul.

Supported q: primes (any), and prime powers
{4, 8, 9, 16, 25, 27, 32}. Extend by adding an entry in
`_PRIME_POWER_IRREDUCIBLES` plus a multiplication table build.
"""

from __future__ import annotations


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _prime_power(n: int):
    """Return (p, e) if n = p^e with e >= 1, else None."""
    if n < 2:
        return None
    for p in range(2, int(n ** 0.5) + 1):
        if _is_prime(p) and n % p == 0:
            m, e = n, 0
            while m % p == 0:
                m //= p
                e += 1
            if m == 1:
                return (p, e)
            return None
    if _is_prime(n):
        return (n, 1)
    return None


# Irreducible polynomial for F_{p^e}: coefficients as tuple, low→high degree.
# e.g. x^3 + x + 1 over F_2 → (1, 1, 0, 1)
# Elements of F_{p^e} are tuples of length e with entries in F_p,
# encoded as integer value = sum(c_i * p^i).
_PRIME_POWER_IRREDUCIBLES: dict[int, dict[str, object]] = {
    4:  {"p": 2, "e": 2, "poly": (1, 1, 1)},                  # x^2 + x + 1
    8:  {"p": 2, "e": 3, "poly": (1, 1, 0, 1)},               # x^3 + x + 1
    9:  {"p": 3, "e": 2, "poly": (1, 0, 1)},                  # x^2 + 1 (irreducible mod 3)
    16: {"p": 2, "e": 4, "poly": (1, 1, 0, 0, 1)},            # x^4 + x + 1
    25: {"p": 5, "e": 2, "poly": (2, 0, 1)},                  # x^2 + 2 (irred mod 5)
    27: {"p": 3, "e": 3, "poly": (1, 2, 0, 1)},               # x^3 + 2x + 1 (irred mod 3)
    32: {"p": 2, "e": 5, "poly": (1, 0, 1, 0, 0, 1)},         # x^5 + x^2 + 1
}


def _int_to_coeffs(x: int, p: int, e: int) -> tuple:
    out = [0] * e
    for i in range(e):
        out[i] = x % p
        x //= p
    return tuple(out)


def _coeffs_to_int(c: tuple, p: int) -> int:
    v = 0
    for i in range(len(c) - 1, -1, -1):
        v = v * p + c[i]
    return v


class FieldPrime:
    def __init__(self, p: int):
        self.q = p
        self.p = p
        self.zero = 0
        self.one = 1

    def add(self, a, b): return (a + b) % self.q
    def sub(self, a, b): return (a - b) % self.q
    def neg(self, a):    return (-a) % self.q
    def mul(self, a, b): return (a * b) % self.q

    def inv(self, a):
        if a == 0:
            raise ZeroDivisionError
        return pow(a, self.q - 2, self.q)

    def elements(self):
        return range(self.q)

    def nonzero(self):
        return range(1, self.q)


class FieldPrimePower:
    """F_{p^e} via polynomial mod irreducible. Elements are p-adic ints in [0, q)."""

    def __init__(self, q: int):
        spec = _PRIME_POWER_IRREDUCIBLES.get(q)
        if spec is None:
            raise NotImplementedError(
                f"F_{q} arithmetic not tabled; add an irreducible to _PRIME_POWER_IRREDUCIBLES"
            )
        self.q = q
        self.p: int = spec["p"]
        self.e: int = spec["e"]
        self.poly: tuple = spec["poly"]  # irreducible, low→high
        self.zero = 0
        self.one = 1
        self._mul_table = self._build_mul_table()
        self._inv_table = self._build_inv_table()

    def _add_coeffs(self, a, b):
        return tuple((a[i] + b[i]) % self.p for i in range(self.e))

    def _sub_coeffs(self, a, b):
        return tuple((a[i] - b[i]) % self.p for i in range(self.e))

    def _poly_mod(self, c: list[int]) -> list[int]:
        """Reduce c (list of length up to 2e-1) mod self.poly in-place, return length-e list."""
        p, e = self.p, self.e
        poly = self.poly  # c_0 + c_1 x + ... + c_e x^e, leading c_e = 1
        # leading is 1 (we chose monic), so each x^e = -(sum poly[i] * x^i for i<e)
        for k in range(len(c) - 1, e - 1, -1):
            ck = c[k]
            if ck == 0:
                continue
            for i in range(e):
                c[k - e + i] = (c[k - e + i] - ck * poly[i]) % p
            c[k] = 0
        return c[:e]

    def _mul_coeffs(self, a, b):
        out = [0] * (2 * self.e - 1)
        for i in range(self.e):
            if a[i] == 0:
                continue
            for j in range(self.e):
                if b[j] == 0:
                    continue
                out[i + j] = (out[i + j] + a[i] * b[j]) % self.p
        out = self._poly_mod(out)
        return tuple(out)

    def _build_mul_table(self):
        t = [[0] * self.q for _ in range(self.q)]
        for x in range(self.q):
            ax = _int_to_coeffs(x, self.p, self.e)
            for y in range(self.q):
                ay = _int_to_coeffs(y, self.p, self.e)
                t[x][y] = _coeffs_to_int(self._mul_coeffs(ax, ay), self.p)
        return t

    def _build_inv_table(self):
        t = {}
        for x in range(1, self.q):
            for y in range(1, self.q):
                if self._mul_table[x][y] == 1:
                    t[x] = y
                    break
        return t

    def add(self, a, b):
        ca = _int_to_coeffs(a, self.p, self.e)
        cb = _int_to_coeffs(b, self.p, self.e)
        return _coeffs_to_int(self._add_coeffs(ca, cb), self.p)

    def sub(self, a, b):
        ca = _int_to_coeffs(a, self.p, self.e)
        cb = _int_to_coeffs(b, self.p, self.e)
        return _coeffs_to_int(self._sub_coeffs(ca, cb), self.p)

    def neg(self, a):
        ca = _int_to_coeffs(a, self.p, self.e)
        return _coeffs_to_int(tuple((-x) % self.p for x in ca), self.p)

    def mul(self, a, b):
        return self._mul_table[a][b]

    def inv(self, a):
        if a == 0:
            raise ZeroDivisionError
        return self._inv_table[a]

    def elements(self):
        return range(self.q)

    def nonzero(self):
        return range(1, self.q)


def field(q: int):
    """Return an F_q arithmetic object for q prime or supported prime power."""
    if _is_prime(q):
        return FieldPrime(q)
    pe = _prime_power(q)
    if pe is None:
        raise ValueError(f"q={q} is not a prime power")
    return FieldPrimePower(q)
