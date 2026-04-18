def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    for i in range(N):
        for f in [2, 3, 5]:
            j = (i + f) % N if (i + f) % N != i else (i * 2 + 1) % N
            edges.add((i, j))
        if N % 3 == 0:
            k = (i + N // 3) % N
            edges.add((i, k))
    return [(u, v) if u < v else (v, u) for u, v in edges]
