def construct(N: int) -> list[tuple[int, int]]:
    edges = []
    k = N // 4
    for i in range(N):
        for j in range(1, k + 1):
            if (i + j) % N != i and (i - j) % N != i:
                edges.append(((i + j) % N, i))
    return list(set(edges))
