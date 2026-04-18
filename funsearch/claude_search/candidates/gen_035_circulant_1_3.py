"""Circulant C(N, {1,3,5}). Parent: gen_002."""

def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    for i in range(N):
        for offset in [1, 3, 5]:
            if offset >= N:
                break
            j = (i + offset) % N
            edges.add((min(i, j), max(i, j)))
    return list(edges)
