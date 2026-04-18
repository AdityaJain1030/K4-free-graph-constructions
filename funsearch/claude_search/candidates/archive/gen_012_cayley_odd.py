def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    offsets = [1, 3]
    if N > 20:
        offsets.append(5)

    for i in range(N):
        for a in offsets:
            edges.add((i, (i + a) % N))
            edges.add((i, (i - a) % N))

    return [(u, v) if u < v else (v, u) for u, v in edges]
