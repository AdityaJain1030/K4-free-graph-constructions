def construct(N: int) -> list[tuple[int, int]]:
    """Cartesian product C_3 □ C_n: vertices are (i,j), i in {0,1,2}, j in {0..N/3-1}."""
    if N % 3 != 0:
        return []

    n = N // 3
    edges = set()

    # Vertices: (i, j) -> vertex ID i*n + j for i in {0,1,2}, j in {0..n-1}
    # Cartesian product edges:
    # 1. Within same j, adjacent i (forms C_3 on i coordinate)
    # 2. Within same i, adjacent j (forms C_n on j coordinate)

    for i in range(3):
        for j in range(n):
            v = i * n + j

            # C_3 structure: connect adjacent i (ring)
            i_next = (i + 1) % 3
            u = i_next * n + j
            if v < u:
                edges.add((v, u))

            # C_n structure: connect adjacent j (ring)
            j_next = (j + 1) % n
            u = i * n + j_next
            if v < u:
                edges.add((v, u))

    return list(edges)
