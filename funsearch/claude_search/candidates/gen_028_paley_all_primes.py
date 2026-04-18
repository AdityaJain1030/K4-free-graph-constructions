"""Paley for all primes: QR for p≡1 mod 4, QNR for p≡3 mod 4."""

def is_prime(n):
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def construct(N: int) -> list[tuple[int, int]]:
    if not is_prime(N) or N == 2:
        return []

    if (N - 1) % 4 == 0:  # N ≡ 1 mod 4: QR
        conn = set()
        for x in range(1, N):
            conn.add((x * x) % N)
    else:  # N ≡ 3 mod 4: QNR
        qr = set()
        for x in range(1, N):
            qr.add((x * x) % N)
        conn = set(range(1, N)) - qr

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            if ((j - i) % N) in conn:
                edges.append((i, j))

    return edges
