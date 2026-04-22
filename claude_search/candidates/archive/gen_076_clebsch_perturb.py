# Family: srg_perturbed
# Catalog: srg_clebsch_minus_matching
# Hypothesis: Clebsch graph (N=16, triangle-free K4-free, α=5) minus matching; extend via tensor product
# Why non-VT: matching deletion breaks Clebsch Aut; tensor product with path breaks regularity further

import random

def construct(N):
    # Clebsch graph: 16 vertices, 5-regular, triangle-free, α=5
    # Vertices = Z_2^4, edges if XOR has exactly 1 or 4 ones
    clebsch = [set() for _ in range(16)]
    for i in range(16):
        for j in range(i+1, 16):
            xor = i ^ j
            w = bin(xor).count('1')
            if w == 1 or w == 4:
                clebsch[i].add(j); clebsch[j].add(i)

    if N == 16:
        # Delete a deterministic matching (not Aut-invariant)
        adj = [s.copy() for s in clebsch]
        for u, v in [(0,1),(2,5),(4,10),(6,9)]:
            if v in adj[u]: adj[u].discard(v); adj[v].discard(u)
        return [(u,v) for u in range(16) for v in adj[u] if v > u]

    # For larger N: take k copies of Clebsch, connect adjacent copies
    # with a K4-free bipartite graph on matching edges
    k = N // 16
    if k < 2 or k * 16 != N: return []

    rng = random.Random(N * 53 + 19)
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    # Within each copy: Clebsch edges
    for layer in range(k):
        off = layer * 16
        for u in range(16):
            for v in clebsch[u]:
                if v > u:
                    adj[off+u].add(off+v); adj[off+v].add(off+u)

    # Between consecutive copies: random matching
    perm = list(range(16))
    for layer in range(k-1):
        off1, off2 = layer*16, (layer+1)*16
        rng.shuffle(perm)
        for u in range(16):
            v = perm[u]
            if not has_k4(off1+u, off2+v):
                adj[off1+u].add(off2+v); adj[off2+v].add(off1+u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
