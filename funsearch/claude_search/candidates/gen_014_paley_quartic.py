def construct(N: int) -> list[tuple[int, int]]:
    """Paley-like using quartic residues (fourth powers mod N)."""
    if N < 3:
        return []

    # Compute quartic residues mod N
    qr = set()
    for x in range(N):
        qr.add((x * x * x * x) % N)

    edges = set()
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in qr and diff != 0:
                edges.add((i, j))

    return list(edges)
