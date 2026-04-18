def construct(N: int) -> list[tuple[int, int]]:
    """Paley-like using sextic residues (sixth powers mod N)."""
    if N < 3:
        return []

    # Compute sextic residues mod N
    sr = set()
    for x in range(N):
        sr.add((x * x * x * x * x * x) % N)

    edges = set()
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in sr and diff != 0:
                edges.add((i, j))

    return list(edges)
