"""Circulant graph C(N, {1,2}) — 4-regular cycle-with-chords.

K4-free for all N >= 5: any 4 vertices must include two at distance >=3 along
the cycle, which are non-adjacent.
"""


def construct(N):
    edges = []
    for i in range(N):
        for k in (1, 2):
            j = (i + k) % N
            a, b = (i, j) if i < j else (j, i)
            edges.append((a, b))
    return list(set(edges))
