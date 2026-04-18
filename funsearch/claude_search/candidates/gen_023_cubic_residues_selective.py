"""Cubic residues on primes where (p-1)/3 <= 12 to stay K4-free."""

def is_prime(n):
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def construct(N: int) -> list[tuple[int, int]]:
    # Target primes where (p-1)/3 <= 12, i.e., p <= 37
    targets = [p for p in range(2, 100) if is_prime(p) and (p-1) % 3 == 0 and (p-1) // 3 <= 12]

    if N not in targets:
        return []

    # Compute cubic residues mod N
    cr = set()
    for x in range(N):
        cr.add((x * x * x) % N)

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in cr and diff != 0:
                edges.append((i, j))

    return edges
