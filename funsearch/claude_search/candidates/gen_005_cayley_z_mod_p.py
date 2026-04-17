"""Cayley graph on Z/pZ for the largest prime p <= N.

For p = 17 (and p ≡ 1 mod 4 where QRs give Paley): use quadratic residues.
For other primes: use a small symmetric subset {±1, ±2}.
Remainder vertices p..N-1 are left isolated.
"""


def construct(N):
    def is_prime(n):
        if n < 2:
            return False
        for d in range(2, int(n ** 0.5) + 1):
            if n % d == 0:
                return False
        return True

    p = max((q for q in range(5, N + 1) if is_prime(q)), default=0)
    if p == 0:
        return []

    if p == 17:
        S = {(x * x) % p for x in range(1, p)}
    else:
        S = {1 % p, 2 % p, (p - 1) % p, (p - 2) % p}

    edges = []
    for i in range(p):
        for j in range(i + 1, p):
            if (j - i) % p in S:
                edges.append((i, j))
    return edges
