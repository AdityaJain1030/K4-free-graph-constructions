def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    a, b = 1, N // 3
    for i in range(N):
        edges.add((i, (i + a) % N))
        edges.add((i, (i + b) % N))
    return [(u, v) if u < v else (v, u) for u, v in edges]
