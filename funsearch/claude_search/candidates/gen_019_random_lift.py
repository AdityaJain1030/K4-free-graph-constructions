"""Random k-lift of the Petersen graph.

For each base edge, pick a random permutation of the k fibers; connect
(u, i) to (v, sigma(i)). Lifts preserve local K4-freeness, so this is
K4-free whenever k | N and Petersen is K4-free (it is).
"""
import random


def construct(N):
    petersen = [(0,1),(1,2),(2,3),(3,4),(4,0),(5,7),(7,9),(9,6),(6,8),
                (8,5),(0,5),(1,6),(2,7),(3,8),(4,9)]
    k = N // 10
    if k < 1:
        return []
    random.seed(N * 101 + 17)
    edges = []
    for u, v in petersen:
        perm = list(range(k))
        random.shuffle(perm)
        for i in range(k):
            a = u * k + i
            b = v * k + perm[i]
            edges.append((min(a, b), max(a, b)))
    return edges
