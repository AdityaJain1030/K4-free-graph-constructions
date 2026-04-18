def construct(N: int) -> list[tuple[int, int]]:
    """Circulant graph with symmetric offset set {1, 2, 3, 4}."""
    if N < 5:
        return []

    edges = set()
    for i in range(N):
        for offset in [1, 2, 3, 4]:
            j = (i + offset) % N
            if i < j:
                edges.add((i, j))

    return list(edges)
