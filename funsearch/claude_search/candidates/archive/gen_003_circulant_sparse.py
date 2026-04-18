def construct(N: int) -> list[tuple[int, int]]:
    edges = []
    offset = N // 3
    for i in range(N):
        j = (i + offset) % N
        if i < j:
            edges.append((i, j))
    return edges
