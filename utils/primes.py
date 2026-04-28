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
