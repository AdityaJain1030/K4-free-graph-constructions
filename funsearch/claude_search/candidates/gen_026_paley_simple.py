"""Paley Cayley on Z/pZ for primes ≡ 1 mod 4. Parent: gen_024 (simplified)."""

def is_prime(n):
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def construct(N: int) -> list[tuple[int, int]]:
    if not is_prime(N) or (N - 1) % 4 != 0:
        return []

    qr = set()
    for x in range(1, N):
        qr.add((x * x) % N)

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            if ((j - i) % N) in qr:
                edges.append((i, j))

    return edges
