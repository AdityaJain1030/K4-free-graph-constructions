"""
search/groups.py
=================
Lightweight group representations for Cayley-graph search. No GAP or
SageMath dependency; elements are hashable tuples/ints, the group
operation and inverse are closures, and inversion orbits over Γ \\ {e}
are precomputed so connection-set search can parametrise over orbit
indicator bits.

Supported families (first-pass, chosen to cover the Parczyk empirical
"groups of order 3·2^k" + the classical Cayley extremizers):

  * cyclic         ℤ_n
  * dihedral       D_{n/2}    (when n even)
  * direct_product ℤ_a × ℤ_b  for any factorisation a·b = n
  * elem_abelian_2 ℤ_2^k       (when n = 2^k)
  * z3_times_2k    ℤ_3 × ℤ_2^k (when n = 3·2^k)

Each factory returns a `GroupSpec`. For each spec, `inversion_orbits`
partitions Γ \\ {e} into sets closed under g ↦ g⁻¹. These are exactly
the atoms of the connection-set search space for *undirected* Cayley
graphs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Callable, Hashable, Iterable


@dataclass
class GroupSpec:
    name: str
    order: int
    elements: list[Hashable]
    identity: Hashable
    inverse_of: dict[Hashable, Hashable]
    op: Callable[[Hashable, Hashable], Hashable]
    # derived / filled by `__post_init__`
    elem_index: dict[Hashable, int] = field(default_factory=dict)
    inversion_orbits: list[tuple[Hashable, ...]] = field(default_factory=list)

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
    # deterministic order
    orbits.sort(key=lambda orb: (len(orb), tuple(G.elem_index[x] for x in orb)))
    return orbits


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


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
    # Elements represented as (r, k) where r ∈ {0,1} is reflection flag
    # and k ∈ ℤ_m is rotation. Multiplication:
    #   (0, a)(0, b) = (0, a+b)
    #   (0, a)(1, b) = (1, a+b)
    #   (1, a)(0, b) = (1, a-b)
    #   (1, a)(1, b) = (0, a-b)
    elems = [(0, k) for k in range(m)] + [(1, k) for k in range(m)]

    def op(x, y):
        ax, bx = x
        ay, by = y
        if ax == 0:
            return (ay, (bx + by) % m)
        else:
            return ((ay + 1) % 2, (bx - by) % m) if False else (
                1 - ay, (bx - by) % m
            )

    def inv(x):
        a, k = x
        if a == 0:
            return (0, (-k) % m)
        return (1, k)  # reflections are self-inverse

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
    inv = {
        (a, b): (A.inverse_of[a], B.inverse_of[b])
        for (a, b) in elems
    }

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
    inv = {x: x for x in elems}  # every element is self-inverse
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


# ---------------------------------------------------------------------------
# Enumerate families for a given order
# ---------------------------------------------------------------------------


def families_of_order(n: int) -> list[GroupSpec]:
    """
    Return a (de-duplicated by name) list of supported group families
    of exact order n. Always includes ℤ_n. For composite n, includes
    direct-product and dihedral variants where applicable.
    """
    out: list[GroupSpec] = []
    seen: set[str] = set()

    def push(spec: GroupSpec):
        if spec.order != n:
            return
        if spec.name in seen:
            return
        seen.add(spec.name)
        out.append(spec)

    push(group_zn(n))

    # Dihedral D_{n/2}: order n when n is even
    if n % 2 == 0 and n >= 4:
        push(group_dihedral(n // 2))

    # Elementary abelian ℤ_2^k
    k = _log2_if_power_of_two(n)
    if k is not None and k >= 2:
        push(group_elem_abelian_2(k))

    # ℤ_3 × ℤ_2^k
    if n % 3 == 0:
        m = n // 3
        k = _log2_if_power_of_two(m)
        if k is not None and k >= 1:
            push(group_z3_times_2k(k))

    # ℤ_a × ℤ_b with a ≤ b, a > 1, a ≠ 1, gcd(a,b) need not be 1
    # (skip a=1 since that reproduces ℤ_n, already pushed).
    for a in range(2, int(n ** 0.5) + 1):
        if n % a != 0:
            continue
        b = n // a
        if a > b:
            continue
        push(group_direct_product(group_zn(a), group_zn(b)))

    return out


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


# ---------------------------------------------------------------------------
# Cayley-graph construction from orbit bitvector
# ---------------------------------------------------------------------------


def cayley_adj_from_bitvec(
    G: GroupSpec,
    bits: Iterable[int],
):
    """
    Build the adjacency matrix (n×n uint8 numpy array) of the Cayley
    graph Cay(Γ, S) where S = union of inversion orbits selected by
    the truthy positions in `bits`. `bits` must have length == G.n_orbits.
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


def connection_set_from_bitvec(
    G: GroupSpec,
    bits: Iterable[int],
) -> list[Hashable]:
    out: list[Hashable] = []
    for b, orbit in zip(bits, G.inversion_orbits):
        if b:
            out.extend(orbit)
    return out
