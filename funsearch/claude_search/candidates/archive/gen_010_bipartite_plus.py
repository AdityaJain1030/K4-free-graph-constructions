def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    half = N // 2

    for i in range(N):
        edges.add((i, (i + half) % N))
        edges.add((i, (i + 1) % N))
        if N % 3 == 0:
            edges.add((i, (i + N // 3) % N))

    return [(u, v) if u < v else (v, u) for u, v in edges]
