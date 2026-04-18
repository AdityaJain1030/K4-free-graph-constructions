"""Paley on {5,13,17} with Legendre symbol. Parent: gen_037."""

def construct(N: int) -> list[tuple[int, int]]:
    if N not in {5, 13, 17}:
        return []
    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            if pow((j - i) % N, (N - 1) // 2, N) == 1:
                edges.append((i, j))
    return edges
