# Family: polarity
"""Polarity graph of PG(2,3): orthogonality in finite projective plane."""

def construct(N):
    if N != 13:
        return []

    # PG(2,3) has 13 points and 13 lines
    # Points: [0, 13), representing 1-d subspaces of F_3^3
    # Use standard coordinates mod 3

    from itertools import combinations

    points = []
    for x in range(3):
        for y in range(3):
            for z in range(3):
                if (x, y, z) != (0, 0, 0):
                    points.append((x, y, z))

    # Normalize to canonical form (divide by first non-zero)
    def normalize(p):
        for c in p:
            if c != 0:
                inv = pow(c, 1, 3)  # Multiplicative inverse mod 3
                return tuple((c * inv) % 3 for c in p)
        return p

    points = list(set(normalize(p) for p in points))[:13]

    edges = []

    # Two points are orthogonal if their dot product is 0 mod 3
    for i, p1 in enumerate(points):
        for j, p2 in enumerate(points):
            if i < j:
                dot = sum(p1[k] * p2[k] for k in range(3)) % 3
                if dot == 0:
                    edges.append((i, j))

    return edges
