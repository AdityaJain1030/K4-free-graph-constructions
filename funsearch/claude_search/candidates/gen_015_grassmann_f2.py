"""Grassmann graph Gr(F_2^n, 2): 2-dim subspaces of F_2^n, adjacent iff meeting in 1-dim.

Contains K4 for n >= 4, so eval will reject most N. Included as family inspiration:
the idea is 'vertices = k-subspaces, edges = meet in codim 1'.
"""
from itertools import combinations


def construct(N):
    n = 3
    while (2 ** n - 1) * (2 ** (n + 1) - 1) // 3 <= N and n < 7:
        n += 1
    dim = n
    vecs = [tuple(1 if (i >> b) & 1 else 0 for b in range(dim))
            for i in range(1, 2 ** dim)]
    # Enumerate 2-dim subspaces: pick two independent vectors, normalize
    subs = set()
    for i in range(len(vecs)):
        for j in range(i + 1, len(vecs)):
            basis = frozenset([vecs[i], vecs[j],
                               tuple((a ^ b) for a, b in zip(vecs[i], vecs[j]))])
            subs.add(basis)
    subs = list(subs)[:N]
    edges = []
    for i in range(len(subs)):
        for j in range(i + 1, len(subs)):
            if len(subs[i] & subs[j]) == 1:
                edges.append((i, j))
    return edges
