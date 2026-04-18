# Family: peisert
"""Peisert-like construction: QR union with special element for primes ≡ 5 mod 8."""

def construct(N):
    if N % 8 != 5:
        return []
    if N < 2 or any(N % i == 0 for i in range(2, int(N**0.5) + 1)):
        return []

    qr = set((i*i) % N for i in range(N))
    special = (-(N-1)//4) % N
    edges = []

    for i in range(N):
        for j in range(i+1, N):
            diff = (j - i) % N
            if diff in qr or diff == special:
                edges.append((i, j))

    return edges
