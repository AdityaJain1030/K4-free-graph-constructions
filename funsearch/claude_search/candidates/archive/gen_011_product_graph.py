def construct(N: int) -> list[tuple[int, int]]:
    """Strong product of C_3 and ring: vertices are (i,j), i in {0,1,2}, j in {0..N/3-1}."""
    if N % 3 != 0:
        return []

    n = N // 3
    edges = set()

    # Vertices: (i, j) -> vertex ID i*n + j for i in {0,1,2}, j in {0..n-1}
    # Strong product: adjacent if differ by 1 in either coordinate (or both)

    for i in range(3):
        for j in range(n):
            v = i * n + j

            # Ring edges: within same i, adjacent j
            j_next = (j + 1) % n
            u = i * n + j_next
            if v < u:
                edges.add((v, u))

            # Between layers: different i
            for i2 in range(i + 1, 3):
                u = i2 * n + j
                edges.add((v, u))

    return list(edges)
