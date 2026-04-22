"""Randomized degree-capped K4-free construction (cap=6).

For each of many shuffled candidate edges, add it only if both endpoints are
below the degree cap and the addition does not create a K4.
"""

import random


def construct(N):
    random.seed(42)
    cap = 6
    deg = [0] * N
    nbr = [set() for _ in range(N)]
    edges = []
    candidates = [(i, j) for i in range(N) for j in range(i + 1, N)]
    random.shuffle(candidates)
    for i, j in candidates:
        if deg[i] >= cap or deg[j] >= cap:
            continue
        # Adding (i,j) creates a K4 iff there exist u,v in N(i) ∩ N(j)
        # with u-v an edge (then {i,j,u,v} is a K4).
        common = nbr[i] & nbr[j]
        if any(v in nbr[u] for u in common for v in common if u < v):
            continue
        edges.append((i, j))
        nbr[i].add(j); nbr[j].add(i)
        deg[i] += 1; deg[j] += 1
    return edges
