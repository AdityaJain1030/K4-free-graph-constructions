def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    offsets = [2, 3]
    if N % 5 != 0:
        offsets.append(5)
    if N % 7 != 0:
        offsets.append(7)

    for i in range(N):
        for f in offsets:
            j = (i + f) % N if (i + f) % N != i else (i * 2 + 1) % N
            edges.add((i, j))
    return [(u, v) if u < v else (v, u) for u, v in edges]
