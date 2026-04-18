# Family: latin_square
"""Latin rectangle graph: cells (i,j,k) with N=n^2, connected if share row or column."""

def construct(N):
    import math

    n = int(math.sqrt(N) + 0.5)
    if n * n != N or n < 3:
        return []

    # Vertices: (i,j) pairs for i,j in [0,n)
    edges = []

    for i1 in range(n):
        for j1 in range(n):
            for i2 in range(n):
                for j2 in range(n):
                    v1 = i1 * n + j1
                    v2 = i2 * n + j2
                    if v1 < v2:
                        # Connected if same row XOR same column (but not both, not neither)
                        same_row = (i1 == i2)
                        same_col = (j1 == j2)
                        if same_row != same_col:
                            edges.append((v1, v2))

    return edges
