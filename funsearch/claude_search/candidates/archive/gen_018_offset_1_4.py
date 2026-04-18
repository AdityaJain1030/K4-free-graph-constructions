def construct(N: int) -> list[tuple[int, int]]:
    """Circulant graph with offset set {1, 4}."""
    if N < 6:
        return []

    edges = set()
    for i in range(N):
        for offset in [1, 4]:
            j = (i + offset) % N
            if i < j:
                edges.add((i, j))

    return list(edges)
