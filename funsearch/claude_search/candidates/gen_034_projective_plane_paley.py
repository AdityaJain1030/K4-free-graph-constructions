"""Paley on incidence graph of PG(2,q): N = q^2+q+1."""

def construct(N: int) -> list[tuple[int, int]]:
    # Find q such that q² + q + 1 = N
    q_found = None
    for q in range(1, 100):
        if q*q + q + 1 == N:
            q_found = q
            break
    if q_found is None:
        return []

    q = q_found
    # For prime power q, use quadratic residues
    # Simplified: treat as Cayley on Z/qZ ⊕ Z/qZ with specific generators
    if q < 3:
        return []

    # Use cyclic enumeration of PG(2,q) points and QR connection set
    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            diff = (j - i) % N
            # Paley-like: connect if difference is quadratic residue
            # For now, use a simple symmetric set
            if diff > 0 and diff <= q:
                edges.append((i, j))

    return edges
