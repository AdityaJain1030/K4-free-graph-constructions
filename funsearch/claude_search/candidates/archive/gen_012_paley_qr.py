def construct(N: int) -> list[tuple[int, int]]:
    """Paley graph: connect vertices whose difference is a quadratic residue."""
    if N < 3:
        return []

    # Compute quadratic residues mod N
    qr = set()
    for x in range(1, N):
        qr.add((x * x) % N)

    edges = set()
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in qr:
                edges.add((i, j))

    return list(edges)
