def construct(N: int) -> list[tuple[int, int]]:
    edges = []
    n = N
    qr = set()
    for i in range(n):
        qr.add((i * i) % n)

    for i in range(n):
        for j in range(i + 1, n):
            diff = (j - i) % n
            if diff in qr and diff != 0:
                edges.append((i, j))
    return edges
