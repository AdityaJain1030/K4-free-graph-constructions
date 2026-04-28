"""
utils/algebra.py
=================
Number-theoretic, field, and group primitives shared across the repo.

Layers (top → bottom):
  * **Primality / multiplicative-group helpers** — `is_prime`,
    `prime_factors`, `prime_power`, `primitive_root`, `smallest_qnr`.
  * **Finite fields** — `field(q)` for any prime or supported prime
    power q ∈ {4, 8, 9, 16, 25, 27, 32}. Returns a `FieldPrime` or
    `FieldPrimePower` with a uniform `(zero, one, elements, nonzero,
    add, sub, neg, mul, inv)` API. All elements are ints in [0, q).
  * **Groups (`GroupSpec`)** — lightweight group representations for
    Cayley-graph search. Factories for cyclic / dihedral / direct-product
    / elementary-abelian / Z_3 × Z_2^k. `families_of_order(n)` enumerates
    all hand-coded families of a given order; `families_of_order_gap(n)`
    enumerates *every* SmallGroup of order n via a GAP shell-out (cached
    under `graphs_src/gap_groups/`).
  * **PSL(2, q)** — `psl2(q)` builds the projective special linear
    group as a `GroupSpec`. Used by the PSL-tabu search and
    `PSLInvolutionsSearch`.
  * **Cayley graph helpers** — `cayley_adj_from_bitvec`,
    `connection_set_from_bitvec`: turn a bitvector over a group's
    inversion orbits into the corresponding Cayley graph adjacency
    matrix.

Element representation for prime-power fields: int x ∈ [0, q) decodes
via base-p digits to a length-e coefficient tuple `(c_0, ..., c_{e-1})`
representing `c_0 + c_1·x + ... + c_{e-1}·x^{e-1}` mod the tabled monic
irreducible.

Extension points:
  * New prime power q: append an entry to `_PRIME_POWER_IRREDUCIBLES`.
  * New group family: write a factory returning `GroupSpec` and (if it
    has a clean closed-form characterisation by order) wire it into
    `families_of_order`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field as _dataclass_field
from itertools import product
from pathlib import Path
from typing import Callable, Hashable, Iterable


# ---------------------------------------------------------------------------
# Primality / multiplicative-group helpers
# ---------------------------------------------------------------------------


def is_prime(n: int) -> bool:
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


def prime_factors(n: int) -> list[int]:
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


def prime_power(n: int) -> tuple[int, int] | None:
    """Return (p, e) if n = p^e with e >= 1 and p prime, else None."""
    if n < 2:
        return None
    for p in range(2, int(n ** 0.5) + 1):
        if is_prime(p) and n % p == 0:
            m, e = n, 0
            while m % p == 0:
                m //= p
                e += 1
            if m == 1:
                return (p, e)
            return None
    if is_prime(n):
        return (n, 1)
    return None


def primitive_root(p: int) -> int:
    """Smallest primitive root mod prime p."""
    phi = p - 1
    qs = prime_factors(phi)
    for g in range(2, p):
        if all(pow(g, phi // q, p) != 1 for q in qs):
            return g
    raise ValueError(f"no primitive root found mod {p}")


def smallest_qnr(q: int) -> int:
    """Smallest quadratic non-residue in F_q for odd prime q."""
    for c in range(2, q):
        if pow(c, (q - 1) // 2, q) == q - 1:
            return c
    raise ValueError(f"no QNR for q={q}")


# ---------------------------------------------------------------------------
# Finite fields
# ---------------------------------------------------------------------------


# Irreducible polynomial for F_{p^e}, low→high degree (monic, leading 1).
# Element x ∈ [0, q) decodes via base-p digits to coefficients
# (c_0, ..., c_{e-1}) representing c_0 + c_1·t + ... + c_{e-1}·t^{e-1} mod poly.
_PRIME_POWER_IRREDUCIBLES: dict[int, dict[str, object]] = {
    4:  {"p": 2, "e": 2, "poly": (1, 1, 1)},                  # x^2 + x + 1
    8:  {"p": 2, "e": 3, "poly": (1, 1, 0, 1)},               # x^3 + x + 1
    9:  {"p": 3, "e": 2, "poly": (1, 0, 1)},                  # x^2 + 1
    16: {"p": 2, "e": 4, "poly": (1, 1, 0, 0, 1)},            # x^4 + x + 1
    25: {"p": 5, "e": 2, "poly": (2, 0, 1)},                  # x^2 + 2
    27: {"p": 3, "e": 3, "poly": (1, 2, 0, 1)},               # x^3 + 2x + 1
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
    """F_p for p prime. Elements are ints in [0, p)."""

    def __init__(self, p: int):
        if not is_prime(p):
            raise ValueError(f"p={p} is not prime")
        self.q = p
        self.p = p
        self.e = 1
        self.zero = 0
        self.one = 1
        self.elements = tuple(range(p))
        self.nonzero = tuple(range(1, p))

    def add(self, a, b): return (a + b) % self.q
    def sub(self, a, b): return (a - b) % self.q
    def neg(self, a):    return (-a) % self.q
    def mul(self, a, b): return (a * b) % self.q

    def inv(self, a):
        if a == 0:
            raise ZeroDivisionError
        return pow(a, self.q - 2, self.q)


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
        self.poly: tuple = spec["poly"]
        self.zero = 0
        self.one = 1
        self.elements = tuple(range(q))
        self.nonzero = tuple(range(1, q))
        self._mul_table = self._build_mul_table()
        self._inv_table = self._build_inv_table()

    def _add_coeffs(self, a, b):
        return tuple((a[i] + b[i]) % self.p for i in range(self.e))

    def _sub_coeffs(self, a, b):
        return tuple((a[i] - b[i]) % self.p for i in range(self.e))

    def _poly_mod(self, c: list[int]) -> list[int]:
        p, e = self.p, self.e
        poly = self.poly
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


def field(q: int):
    """Return an F_q arithmetic object for q prime or supported prime power."""
    if is_prime(q):
        return FieldPrime(q)
    pe = prime_power(q)
    if pe is None:
        raise ValueError(f"q={q} is not a prime power")
    return FieldPrimePower(q)


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


@dataclass
class GroupSpec:
    name: str
    order: int
    elements: list[Hashable]
    identity: Hashable
    inverse_of: dict[Hashable, Hashable]
    op: Callable[[Hashable, Hashable], Hashable]
    # derived / filled by `__post_init__`
    elem_index: dict[Hashable, int] = _dataclass_field(default_factory=dict)
    inversion_orbits: list[tuple[Hashable, ...]] = _dataclass_field(default_factory=list)

    def __post_init__(self):
        if not self.elem_index:
            self.elem_index = {e: i for i, e in enumerate(self.elements)}
        if not self.inversion_orbits:
            self.inversion_orbits = _compute_inversion_orbits(self)

    @property
    def n_orbits(self) -> int:
        return len(self.inversion_orbits)


def _compute_inversion_orbits(G: GroupSpec) -> list[tuple[Hashable, ...]]:
    """Orbits of g ↦ g⁻¹ on Γ \\ {e}."""
    seen: set = set()
    orbits: list[tuple[Hashable, ...]] = []
    for g in G.elements:
        if g == G.identity or g in seen:
            continue
        gi = G.inverse_of[g]
        if g == gi:
            orbits.append((g,))
            seen.add(g)
        else:
            orbits.append((g, gi))
            seen.update((g, gi))
    orbits.sort(key=lambda orb: (len(orb), tuple(G.elem_index[x] for x in orb)))
    return orbits


# ── hand-coded family factories ──────────────────────────────────────────────


def group_zn(n: int) -> GroupSpec:
    elems = list(range(n))
    inv = {g: (-g) % n for g in elems}
    return GroupSpec(
        name=f"Z{n}",
        order=n,
        elements=elems,
        identity=0,
        inverse_of=inv,
        op=lambda a, b: (a + b) % n,
    )


def group_dihedral(m: int) -> GroupSpec:
    """D_m — symmetries of m-gon; order 2m."""
    elems = [(0, k) for k in range(m)] + [(1, k) for k in range(m)]

    def op(x, y):
        ax, bx = x
        ay, by = y
        if ax == 0:
            return (ay, (bx + by) % m)
        return (1 - ay, (bx - by) % m)

    def inv(x):
        a, k = x
        if a == 0:
            return (0, (-k) % m)
        return (1, k)

    return GroupSpec(
        name=f"D{m}",
        order=2 * m,
        elements=elems,
        identity=(0, 0),
        inverse_of={x: inv(x) for x in elems},
        op=op,
    )


def group_direct_product(A: GroupSpec, B: GroupSpec) -> GroupSpec:
    elems = [(a, b) for a in A.elements for b in B.elements]
    inv = {(a, b): (A.inverse_of[a], B.inverse_of[b]) for (a, b) in elems}

    def op(x, y):
        return (A.op(x[0], y[0]), B.op(x[1], y[1]))

    return GroupSpec(
        name=f"{A.name}x{B.name}",
        order=A.order * B.order,
        elements=elems,
        identity=(A.identity, B.identity),
        inverse_of=inv,
        op=op,
    )


def group_elem_abelian_2(k: int) -> GroupSpec:
    """ℤ_2^k."""
    if k <= 0:
        return GroupSpec(
            name="Z2^0",
            order=1,
            elements=[()],
            identity=(),
            inverse_of={(): ()},
            op=lambda a, b: (),
        )
    elems = list(product([0, 1], repeat=k))
    inv = {x: x for x in elems}
    return GroupSpec(
        name=f"Z2^{k}",
        order=2 ** k,
        elements=elems,
        identity=tuple([0] * k),
        inverse_of=inv,
        op=lambda a, b: tuple((x + y) % 2 for x, y in zip(a, b)),
    )


def group_z3_times_2k(k: int) -> GroupSpec:
    """ℤ_3 × ℤ_2^k — Parczyk's empirical sweet-spot family."""
    A = group_zn(3)
    B = group_elem_abelian_2(k)
    spec = group_direct_product(A, B)
    spec.name = f"Z3xZ2^{k}"
    return spec


def _log2_if_power_of_two(n: int) -> int | None:
    if n <= 0:
        return None
    k = 0
    m = n
    while m > 1:
        if m % 2 != 0:
            return None
        m //= 2
        k += 1
    return k


def families_of_order(n: int) -> list[GroupSpec]:
    """Hand-coded supported families of exact order n (deduplicated by name)."""
    out: list[GroupSpec] = []
    seen: set[str] = set()

    def push(spec: GroupSpec):
        if spec.order != n or spec.name in seen:
            return
        seen.add(spec.name)
        out.append(spec)

    push(group_zn(n))
    if n % 2 == 0 and n >= 4:
        push(group_dihedral(n // 2))
    k = _log2_if_power_of_two(n)
    if k is not None and k >= 2:
        push(group_elem_abelian_2(k))
    if n % 3 == 0:
        m = n // 3
        k = _log2_if_power_of_two(m)
        if k is not None and k >= 1:
            push(group_z3_times_2k(k))
    for a in range(2, int(n ** 0.5) + 1):
        if n % a != 0:
            continue
        b = n // a
        if a > b:
            continue
        push(group_direct_product(group_zn(a), group_zn(b)))
    return out


# ── Cayley graph helpers ────────────────────────────────────────────────────


def cayley_adj_from_bitvec(G: GroupSpec, bits: Iterable[int]):
    """
    Adjacency matrix (n×n uint8 numpy array) of the Cayley graph Cay(Γ, S)
    where S is the union of inversion orbits selected by truthy `bits`.
    """
    import numpy as np
    n = G.order
    bits = list(bits)
    assert len(bits) == G.n_orbits

    S: list[Hashable] = []
    for b, orbit in zip(bits, G.inversion_orbits):
        if b:
            S.extend(orbit)

    adj = np.zeros((n, n), dtype=np.uint8)
    for i, g in enumerate(G.elements):
        for s in S:
            h = G.op(g, s)
            j = G.elem_index[h]
            if i != j:
                adj[i, j] = 1
                adj[j, i] = 1
    return adj


def connection_set_from_bitvec(G: GroupSpec, bits: Iterable[int]) -> list[Hashable]:
    out: list[Hashable] = []
    for b, orbit in zip(bits, G.inversion_orbits):
        if b:
            out.extend(orbit)
    return out


# ---------------------------------------------------------------------------
# GAP SmallGroups bridge
# ---------------------------------------------------------------------------


_REPO = Path(__file__).resolve().parent.parent
_GAP_CACHE_DIR = _REPO / "graphs_src" / "gap_groups"

# Safety cap. Orders with more than this many SmallGroups are refused.
MAX_GROUPS_PER_N = 500


def _gap_binary() -> str:
    path = shutil.which("gap")
    if path:
        return path
    raise RuntimeError(
        "GAP binary `gap` not found on PATH. Install via:\n"
        "    micromamba install -n k4free -c conda-forge gap-defaults\n"
        "and re-activate the env (`micromamba activate k4free`)."
    )


_GAP_SCRIPT_TEMPLATE = r"""
SizeScreen([32768, 32768]);;
n := {n};;
nsg := NumberSmallGroups(n);;
if nsg > {cap} then
    Print("CAP ", nsg, "\n");
    QUIT_GAP();
fi;
for k in [1..nsg] do
    g := SmallGroup(n, k);
    elts := Elements(g);
    sd := StructureDescription(g);
    Print("BEGIN\n");
    Print("ID ", n, " ", k, "\n");
    Print("SD ", sd, "\n");
    for i in [1..n] do
        Print("ROW");
        for j in [1..n] do
            Print(" ", Position(elts, elts[i] * elts[j]) - 1);
        od;
        Print("\n");
    od;
    Print("END\n");
od;
QUIT_GAP();
"""


def _gap_dump_order(n: int) -> list[dict]:
    """Shell out to GAP, return list of {id, sd, mult} dicts for SmallGroup(n, *)."""
    if n <= 0:
        return []
    import tempfile

    script = _GAP_SCRIPT_TEMPLATE.format(n=n, cap=MAX_GROUPS_PER_N)
    with tempfile.NamedTemporaryFile(
        "w", suffix=".g", delete=False, prefix=f"gap_n{n}_"
    ) as fh:
        fh.write(script)
        script_path = fh.name
    try:
        proc = subprocess.run(
            [_gap_binary(), "-q", "-b", script_path],
            capture_output=True,
            text=True,
            timeout=600,
        )
    finally:
        try:
            os.unlink(script_path)
        except OSError:
            pass
    if proc.returncode != 0:
        raise RuntimeError(
            f"GAP failed (rc={proc.returncode}) for n={n}:\n"
            f"stderr:\n{proc.stderr}\nstdout head:\n{proc.stdout[:500]}"
        )
    return _parse_gap_output(n, proc.stdout)


def _parse_gap_output(n: int, text: str) -> list[dict]:
    groups: list[dict] = []
    current: dict | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("CAP "):
            nsg = int(line.split()[1])
            print(
                f"[gap_groups] skipping n={n}: {nsg} SmallGroups exceeds "
                f"cap MAX_GROUPS_PER_N={MAX_GROUPS_PER_N}.",
                flush=True,
            )
            return []
        if line == "BEGIN":
            current = {"id": None, "sd": None, "mult": []}
            continue
        if current is None:
            continue
        if line.startswith("ID "):
            _, nn, kk = line.split()
            current["id"] = [int(nn), int(kk)]
        elif line.startswith("SD "):
            current["sd"] = line[3:].strip()
        elif line.startswith("ROW"):
            row = [int(x) for x in line[3:].split()]
            if len(row) != n:
                raise RuntimeError(
                    f"GAP emitted row of length {len(row)} != n={n} for "
                    f"id={current.get('id')}"
                )
            current["mult"].append(row)
        elif line == "END":
            if len(current["mult"]) != n:
                raise RuntimeError(
                    f"GAP emitted {len(current['mult'])} rows != n={n} "
                    f"for id={current.get('id')}"
                )
            groups.append(current)
            current = None
    return groups


def _gap_cache_path(n: int) -> Path:
    return _GAP_CACHE_DIR / f"n_{n:04d}.json"


def load_order(n: int, *, force: bool = False) -> list[dict]:
    """Cached GAP dump for order n; regenerated if missing or `force=True`."""
    path = _gap_cache_path(n)
    if path.exists() and not force:
        with path.open() as fh:
            return json.load(fh)
    groups = _gap_dump_order(n)
    _GAP_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w") as fh:
        json.dump(groups, fh)
    tmp.replace(path)
    return groups


def _spec_name_from_gap(n_k: Iterable[int], sd: str) -> str:
    n, k = int(n_k[0]), int(n_k[1])
    safe = sd.replace(" ", "")
    return f"SG_{n}_{k}_{safe}"


def to_group_spec(entry: dict) -> GroupSpec:
    """Build a GroupSpec from a GAP-dumped {id, sd, mult} entry."""
    n_k = entry["id"]
    n = n_k[0]
    sd = entry["sd"]
    mult = entry["mult"]

    identity = -1
    for i, row in enumerate(mult):
        if row == list(range(n)):
            identity = i
            break
    if identity < 0:
        raise RuntimeError(f"no identity row in GAP dump for SmallGroup{tuple(n_k)}")

    inverse_of: dict[int, int] = {}
    for i in range(n):
        row = mult[i]
        j = None
        for jj in range(n):
            if row[jj] == identity:
                j = jj
                break
        if j is None:
            raise RuntimeError(
                f"no inverse for element {i} in SmallGroup{tuple(n_k)}"
            )
        inverse_of[i] = j

    def op(a: int, b: int, _mult=mult) -> int:
        return _mult[a][b]

    return GroupSpec(
        name=_spec_name_from_gap(n_k, sd),
        order=n,
        elements=list(range(n)),
        identity=identity,
        inverse_of=inverse_of,
        op=op,
    )


def families_of_order_gap(n: int, *, force: bool = False) -> list[GroupSpec]:
    """Drop-in replacement for `families_of_order(n)` backed by GAP SmallGroups."""
    entries = load_order(n, force=force)
    return [to_group_spec(e) for e in entries]


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
    """For det=1 matrices: inv((a,b;c,d)) = (d,-b;-c,a)."""
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
                if a != fq.zero:
                    ainv = fq.inv(a)
                    d = fq.mul(ainv, fq.add(fq.one, fq.mul(b, c)))
                    yield ((a, b), (c, d))
                else:
                    if b == fq.zero:
                        continue
                    binv = fq.inv(b)
                    c_required = fq.neg(binv)
                    if c != c_required:
                        continue
                    for d in fq.elements:
                        yield ((a, b), (c, d))


def psl2(q: int) -> GroupSpec:
    """Build PSL(2, q) as a GroupSpec, q ∈ {prime, supported prime power}."""
    fq = field(q)

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
