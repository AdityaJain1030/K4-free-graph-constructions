def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    a = N // 5
    b = N - a

    for i in range(N):
        for j in range(i + 1, N):
            i1, i2 = i % a, i // a
            j1, j2 = j % a, j // a

            if (i1 + 1) % a == j1 and i2 == j2:
                edges.add((i, j))
            elif i1 == j1 and (i2 + 1) % (b // a) == j2:
                edges.add((i, j))
            elif (i1 + 2) % a == j1 and (i2 + 1) % (b // a) == j2:
                edges.add((i, j))

    return list(edges)
