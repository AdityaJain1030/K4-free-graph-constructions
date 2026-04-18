def construct(N: int) -> list[tuple[int, int]]:
    edges = []
    if N < 3 or N % 2 == 0:
        return edges

    factors = [2, 3]
    for i in range(1, N):
        for f in factors:
            j = (i * f) % N
            if i < j:
                edges.append((i, j))
    return edges
