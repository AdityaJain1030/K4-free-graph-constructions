"""Hybrid: Paley on primes ≡ 1 mod 4, else circulant C(N, {1,2}). Family: crossover."""

def is_prime(n):
    if n < 2: return False
    if n == 2: return True
    if n % 2 == 0: return False
    for i in range(3, int(n**0.5) + 1, 2):
        if n % i == 0:
            return False
    return True

def construct(N: int) -> list[tuple[int, int]]:
    if is_prime(N) and (N - 1) % 4 == 0:
        # Paley: QR
        qr = {(x * x) % N for x in range(1, N)}
        edges = []
        for i in range(N):
            for j in range(i + 1, N):
                if ((j - i) % N) in qr:
                    edges.append((i, j))
    else:
        # Circulant {1, 2}
        edges = []
        for i in range(N):
            for offset in [1, 2]:
                j = (i + offset) % N
                if i < j:
                    edges.append((i, j))
                else:
                    edges.append((j, i))

    return list(set(edges))
