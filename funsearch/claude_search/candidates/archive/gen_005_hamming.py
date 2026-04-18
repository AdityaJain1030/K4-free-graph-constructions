def construct(N: int) -> list[tuple[int, int]]:
    """Connect vertices whose binary representations differ in exactly 2 bits."""
    edges = set()

    for i in range(N):
        for j in range(i + 1, N):
            # Count bit differences
            xor = i ^ j
            hamming = bin(xor).count('1')
            if hamming == 2:
                edges.add((i, j))

    return list(edges)
