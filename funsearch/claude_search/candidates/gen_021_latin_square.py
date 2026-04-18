"""Latin square graph L(n): vertices = n^2 cells, adjacent iff same row, column, or symbol.

Each vertex has 3(n-1) neighbors; contains triangles (row/col/symbol triples)
and often K4. Eval will reject most N — included as a combinatorial-design
family exemplar.
"""


def construct(N):
    n = 2
    while (n + 1) * (n + 1) <= N:
        n += 1
    if n * n > N or n < 3:
        return []
    # Use cyclic Latin square: L[i][j] = (i + j) mod n
    cells = [(i, j, (i + j) % n) for i in range(n) for j in range(n)]
    edges = []
    for x in range(n * n):
        r1, c1, s1 = cells[x]
        for y in range(x + 1, n * n):
            r2, c2, s2 = cells[y]
            if r1 == r2 or c1 == c2 or s1 == s2:
                edges.append((x, y))
    return edges
