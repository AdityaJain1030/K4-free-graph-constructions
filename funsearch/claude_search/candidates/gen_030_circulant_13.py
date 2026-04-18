"""Circulant C(N, {1,3}). Parent: gen_002."""

def construct(N: int) -> list[tuple[int, int]]:
    edges = []
    for i in range(N):
        for offset in [1, 3]:
            j = (i + offset) % N
            if i < j:
                edges.append((i, j))
            else:
                edges.append((j, i))
    return list(set(edges))
