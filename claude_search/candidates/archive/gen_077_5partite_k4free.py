# Family: structure_plus_noise
# Catalog: bohman_keevash_k4_process
# Parent: gen_059_k4free_nocap (5-partite structure forces α=N/5; random K4-free edges between parts)
# Hypothesis: 5-partite base ensures α=N/5=7 at N=35 with d_max=6; c=7*6/(35*ln6)=0.683<0.6789
# Why non-VT: random permutations between parts destroy all symmetry

import random

def construct(N):
    if N % 5 != 0: return []
    k = N // 5
    groups = [list(range(i*k, (i+1)*k)) for i in range(5)]
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    rng = random.Random(N * 79 + 37)
    cap = max(4, int(N**0.5) - 1)

    # Between each pair of groups: shuffle and add K4-free edges up to degree cap
    pairs = [(gi, gj) for gi in range(5) for gj in range(gi+1, 5)]
    for gi, gj in pairs:
        edges = [(u, v) for u in groups[gi] for v in groups[gj]]
        rng.shuffle(edges)
        for u, v in edges:
            if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
                adj[u].add(v); adj[v].add(u)

    return [(u, v) for u in range(N) for v in adj[u] if v > u]
