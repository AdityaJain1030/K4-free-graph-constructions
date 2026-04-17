"""Petersen graph vertex-blowup.

Replace each of Petersen's 10 vertices with an independent set of size k=floor(N/10).
If two Petersen vertices are adjacent, add all bipartite edges between their
blow-up sets. The result is K4-free (since Petersen is K4-free and blow-up of a
K4-free graph by independent sets remains K4-free — any 4-clique would require
4 pairwise-adjacent blocks forming a K4 in Petersen, impossible).
Remainder vertices are distributed into existing blocks as extra IS members.
"""


def construct(N):
    P = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0),
         (5, 7), (7, 9), (9, 6), (6, 8), (8, 5),
         (0, 5), (1, 6), (2, 7), (3, 8), (4, 9)]
    if N < 10:
        return []
    k, r = divmod(N, 10)
    block_size = [k + (1 if b < r else 0) for b in range(10)]
    start = [0] * 10
    for b in range(1, 10):
        start[b] = start[b - 1] + block_size[b - 1]
    edges = []
    for u, v in P:
        for i in range(block_size[u]):
            for j in range(block_size[v]):
                edges.append((start[u] + i, start[v] + j))
    return edges
