# Family: random_process
# Catalog: bohman_keevash_k4_process
# Parent: gen_013_bohman_keevash (add degree cap to prevent high-degree vertices dominating)
# Hypothesis: degree-capped K4-free process gives more uniform degrees, smaller α, better c
# Why non-VT: seeded order + degree cap creates degree-heterogeneous graph with no transitive Aut

import random

def construct(N):
    """K4-free process with degree cap at sqrt(N)+2 to keep α small."""
    cap = int(N**0.5) + 2
    rng = random.Random(N * 43 + 11)
    adj = [set() for _ in range(N)]

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    pairs=[(i,j) for i in range(N) for j in range(i+1,N)]
    rng.shuffle(pairs)
    for u,v in pairs:
        if len(adj[u])<cap and len(adj[v])<cap and not has_k4(u,v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
