# Family: random_process
# Catalog: bohman_keevash_k4_process
# Parent: gen_026_bohman_degree_cap (cap at sqrt(N)+4 instead of +2; denser graph for smaller α)
# Hypothesis: larger degree cap allows denser K4-free graph; α/d_max ratio may decrease
# Why non-VT: seeded random order + higher degree cap creates more irregular degree distribution

import random

def construct(N):
    cap = int(N**0.5) + 4
    rng = random.Random(N * 43 + 11)
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    pairs = [(i,j) for i in range(N) for j in range(i+1,N)]
    rng.shuffle(pairs)
    for u, v in pairs:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
