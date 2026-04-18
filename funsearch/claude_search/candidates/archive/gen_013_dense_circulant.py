def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    for i in range(N):
        for a in [1, 2, 3, 4]:
            if a < N // 2:
                edges.add((i, (i + a) % N))
                edges.add((i, (i - a) % N))
    return [(u, v) if u < v else (v, u) for u, v in edges]
