"""Kneser graph K(2k+1, k). Vertices = k-subsets of {0..2k}, edges = disjoint pairs.

Triangle-free for k >= 2 (needs 3k <= 2k+1, impossible), so K4-free.
K(5,2) = Petersen. K(7,3) has 35 vertices. K(9,4) has 126.
"""
from itertools import combinations


def _binom(n, k):
    r = 1
    for i in range(k):
        r = r * (n - i) // (i + 1)
    return r


def construct(N):
    k = 2
    while _binom(2 * (k + 1) + 1, k + 1) <= N:
        k += 1
    m = _binom(2 * k + 1, k)
    if m > N or m < 4:
        return []
    subs = list(combinations(range(2 * k + 1), k))
    edges = []
    for i in range(m):
        sa = set(subs[i])
        for j in range(i + 1, m):
            if not sa & set(subs[j]):
                edges.append((i, j))
    return edges
