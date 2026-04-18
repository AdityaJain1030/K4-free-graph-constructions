def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    for i in range(N):
        for f in [2, 3, 7]:
            j = (i + f) % N if (i + f) % N != i else (i * 2 + 1) % N
            edges.add((i, j))
    return [(u, v) if u < v else (v, u) for u, v in edges]
