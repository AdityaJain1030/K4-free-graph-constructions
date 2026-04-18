def construct(N: int) -> list[tuple[int, int]]:
    """Paley-like using cubic residues (third powers mod N)."""
    if N < 3:
        return []

    # Compute cubic residues mod N
    cr = set()
    for x in range(N):
        cr.add((x * x * x) % N)

    edges = set()
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in cr and diff != 0:
                edges.add((i, j))

    return list(edges)
