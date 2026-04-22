# Family: structure_plus_noise
# Parent: none
# Hypothesis: Seeded-random greedy K4-free extension. Shuffle all (i, j) edge
#   candidates under a fixed RNG seed, then add each one iff it does not
#   close a K4 with the currently accepted edges. The resulting graph is
#   maximal K4-free for that ordering, dense (typically close to the K4-free
#   Turán bound), and generically has trivial automorphism group. Gives a
#   non-algebraic baseline at d_max well above any sparse algebraic seed.
#   Agents can mutate by changing the seed, gating edge acceptance by a
#   deterministic rule, or running greedy from a partial algebraic skeleton.
# Why non-VT: the seeded edge order has no translation, permutation, or
#   algebraic invariance. Two vertices i and j are indistinguishable only
#   by accident of the RNG; the expected automorphism group is trivial.

import random


def construct(N):
    if N < 7 or N > 120:
        return []
    rng = random.Random(2026 + N)
    pool = [(i, j) for i in range(N) for j in range(i + 1, N)]
    rng.shuffle(pool)
    adj = [set() for _ in range(N)]
    edges = []
    for u, v in pool:
        common = adj[u] & adj[v]
        has_k4 = False
        for w in common:
            if adj[w] & common:
                has_k4 = True
                break
        if not has_k4:
            adj[u].add(v)
            adj[v].add(u)
            edges.append((u, v))
    return edges
