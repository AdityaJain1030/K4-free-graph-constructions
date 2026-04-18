def construct(N: int) -> list[tuple[int, int]]:
    """Union of cubic and quadratic residues mod N."""
    if N < 3:
        return []

    # Compute cubic and quadratic residues mod N
    cr = set()
    qr = set()
    for x in range(N):
        cr.add((x * x * x) % N)
        qr.add((x * x) % N)

    edges = set()
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff != 0 and (diff in cr or diff in qr):
                edges.add((i, j))

    return list(edges)
