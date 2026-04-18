"""Paley on primes ≡ 1 mod 4 and their powers."""

def is_prime(n):
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def is_prime_power(n):
    """Check if n = p^k for prime p, k >= 1."""
    if n < 2: return False
    for p in range(2, int(n**0.5) + 1):
        if is_prime(p):
            pk = p
            while pk < n:
                pk *= p
            if pk == n:
                return p
    return n if is_prime(n) else None

def construct(N: int) -> list[tuple[int, int]]:
    p = is_prime_power(N)
    # Only works on prime powers ≡ 1 mod 4
    if not p or (p - 1) % 4 != 0:
        return []

    # Quadratic residues mod N in multiplicative group (Z/NZ)*
    qr = set()
    for x in range(1, N):
        qr.add((x * x) % N)

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff != 0 and diff in qr:
                edges.append((i, j))

    return edges
