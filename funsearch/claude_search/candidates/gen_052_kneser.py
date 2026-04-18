# Family: kneser
"""Kneser graphs K(2k+1, k) — vertices are k-subsets of [2k+1], edges connect disjoint pairs."""

def construct(N):
    import math
    from itertools import combinations
    for k in range(1, 8):
        n = 2 * k + 1
        if math.comb(n, k) == N:
            subsets = list(combinations(range(n), k))
            edges = []
            for i, u in enumerate(subsets):
                for j, v in enumerate(subsets):
                    if i < j and len(set(u) & set(v)) == 0:
                        edges.append((i, j))
            return edges
    return []
