def construct(N: int) -> list[tuple[int, int]]:
    """Circulant graph with offset set {2, 3}."""
    if N < 5:
        return []

    edges = set()
    for i in range(N):
        for offset in [2, 3]:
            j = (i + offset) % N
            if i < j:
                edges.add((i, j))

    return list(edges)
