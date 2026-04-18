"""Paley on N in {5,13,17,25,49,121,169}. Parent: gen_026."""

def construct(N: int) -> list[tuple[int, int]]:
    # Known good N values: 5, 13, 17 are small primes ≡ 1 mod 4
    # Try adding: 25=5², 49=7², 121=11², 169=13²
    targets = {5, 13, 17, 25, 49, 121, 169}
    if N not in targets:
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
