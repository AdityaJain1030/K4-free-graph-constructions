def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    for i in range(N):
        offset = 1 + (i % 3)
        edges.add((i, (i + offset) % N))
        edges.add((i, (i - offset) % N))
    return [(u, v) if u < v else (v, u) for u, v in edges]
