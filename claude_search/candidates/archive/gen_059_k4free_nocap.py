# Family: random_process
# Catalog: bohman_keevash_k4_process
# Parent: gen_026_bohman_degree_cap (remove degree cap entirely; pure Bohman-Keevash process)
# Hypothesis: uncapped process achieves theoretical α=O(n^{1/2}) giving c→0 at large N
# Why non-VT: random edge order creates non-uniform degrees; Aut trivial for generic random graph

import random

def construct(N):
    rng = random.Random(N * 71 + 23)
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = adj[u] & adj[v]
        for a in common:
            if common & adj[a] - {a}: return True
        return False

    pairs = [(i,j) for i in range(N) for j in range(i+1,N)]
    rng.shuffle(pairs)
    for u, v in pairs:
        if not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
