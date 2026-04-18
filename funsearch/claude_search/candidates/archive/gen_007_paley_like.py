def construct(N: int) -> list[tuple[int, int]]:
    edges = []
    if N < 3:
        return edges

    residues = set()
    for i in range(N):
        residues.add((i * i) % N)

    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in residues and diff != 0 and diff != N - diff:
                edges.append((i, j))
    return edges
