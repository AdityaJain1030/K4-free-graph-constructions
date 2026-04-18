"""Paley graphs on primes ≡ 1 mod 4."""

def is_prime(n):
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def construct(N: int) -> list[tuple[int, int]]:
    # Only works on primes ≡ 1 mod 4
    if not is_prime(N) or (N - 1) % 4 != 0:
        return []

    # Quadratic residues mod N
    qr = {(x * x) % N for x in range(1, N)}

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in qr:
                edges.append((i, j))

    return edges
