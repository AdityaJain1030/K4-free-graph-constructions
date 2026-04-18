def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    for i in range(N):
        for f in [2, 3]:
            edges.add((i, (i + f) % N))
            edges.add((i, (i - f) % N))
        edges.add((i, (i + 5) % N))
    return [(u, v) if u < v else (v, u) for u, v in edges]
