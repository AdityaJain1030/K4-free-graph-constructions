def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    if N % 2 == 0:
        return []
    k = (N - 1) // 2
    for i in range(N):
        for a in [1, 2]:
            edges.add((i, (i + a) % N))
            edges.add((i, (i - a) % N))
    return [(u, v) if u < v else (v, u) for u, v in edges]
