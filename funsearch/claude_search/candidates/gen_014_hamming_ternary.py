"""Hamming graph H(d, 3): vertices = F_3^d, edges = Hamming distance 1.

Max clique = 3 (varying one coordinate over {0,1,2}), so K4-free.
Vertex count = 3^d: 9 (d=2), 27 (d=3), 81 (d=4).
"""
from itertools import product


def construct(N):
    d = 1
    while 3 ** (d + 1) <= N:
        d += 1
    if d < 2 or 3 ** d > N:
        return []
    m = 3 ** d
    verts = list(product(range(3), repeat=d))
    idx = {v: i for i, v in enumerate(verts)}
    edges = []
    for i, v in enumerate(verts):
        for pos in range(d):
            for val in range(3):
                if val == v[pos]:
                    continue
                w = v[:pos] + (val,) + v[pos + 1:]
                j = idx[w]
                if j > i:
                    edges.append((i, j))
    return edges
