# Family: product
"""Cartesian product of two cycles C_m □ C_n. Bipartite => K4-free."""

def construct(N):
    import math
    for m in range(2, int(math.sqrt(N)) + 2):
        if N % m == 0:
            n = N // m
            if n >= 2:
                edges = []
                for i in range(m):
                    for j in range(n):
                        u = i * n + j
                        # Edge along C_m
                        v = ((i + 1) % m) * n + j
                        if u < v:
                            edges.append((u, v))
                        # Edge along C_n
                        v = i * n + ((j + 1) % n)
                        if u < v:
                            edges.append((u, v))
                return edges
    return []
