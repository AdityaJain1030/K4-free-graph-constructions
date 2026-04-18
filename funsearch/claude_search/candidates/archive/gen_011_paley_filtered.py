def construct(N: int) -> list[tuple[int, int]]:
    edges = []
    qr = {(i * i) % N for i in range(N)}

    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if 0 < diff < N // 2 and diff in qr:
                edges.append((i, j))
    return edges
