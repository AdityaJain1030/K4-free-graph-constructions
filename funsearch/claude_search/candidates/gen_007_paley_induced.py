def construct(N: int) -> list[tuple[int, int]]:
    # Find next prime >= N with p ≡ 1 mod 4
    def is_prime(n):
        if n < 2: return False
        for i in range(2, int(n**0.5)+1):
            if n % i == 0: return False
        return True
    p = N
    while not (is_prime(p) and p % 4 == 1):
        p += 1
    qr = set((i*i) % p for i in range(1, p))
    edges = []
    for i in range(N):
        for j in range(i+1, N):
            if (j - i) % p in qr:
                edges.append((i, j))
    return edges
