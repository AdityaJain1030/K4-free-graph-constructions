"""Cubic residues on all N where (p-1)/3 divides evenly. Parent: gen_023."""

def construct(N: int) -> list[tuple[int, int]]:
    # Only if (N-1) is divisible by 3 (for simplicity, work on all N with this property)
    if (N - 1) % 3 != 0:
        return []

    # Compute cubic residues mod N
    cr = set()
    for x in range(N):
        cr.add((x * x * x) % N)

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            if diff in cr and diff != 0:
                edges.append((i, j))

    return edges
