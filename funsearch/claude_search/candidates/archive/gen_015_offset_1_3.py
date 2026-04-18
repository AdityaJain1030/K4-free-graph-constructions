def construct(N: int) -> list[tuple[int, int]]:
    """Circulant graph with offset set {1, 3}."""
    if N < 5:
        return []

    edges = set()
    for i in range(N):
        for offset in [1, 3]:
            j = (i + offset) % N
            if i < j:
                edges.add((i, j))

    return list(edges)
