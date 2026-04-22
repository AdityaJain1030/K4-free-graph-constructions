# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: gen_020_core_periphery (split N vertices into multiple orbits with different degree levels)
# Hypothesis: 3-orbit construction at any N with different cross-orbit edge densities creates small-α graph
# Why non-VT: three vertex classes with different roles → no automorphism mapping all vertices to all others

import random

def construct(N):
    """Three-orbit non-VT construction: split N into A(N//3), B(N//3), C(N-2*N//3).
    A-B: K4-free bipartite dense; B-C: sparse; A-C: medium; no intra-class edges (bipartite-ish).
    """
    a_size = N // 3
    b_size = N // 3
    c_size = N - a_size - b_size
    if a_size < 5 or b_size < 5: return []

    A = list(range(a_size))
    B = list(range(a_size, a_size + b_size))
    C = list(range(a_size + b_size, N))

    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    rng = random.Random(N * 71 + 37)

    # A-B: dense connections (50% of pairs, K4-free checked)
    ab_pairs = [(a,b) for a in A for b in B]
    rng.shuffle(ab_pairs)
    for u,v in ab_pairs[:len(ab_pairs)//2]:
        if not has_k4(u,v): adj[u].add(v); adj[v].add(u)

    # B-C: medium connections (30%)
    bc_pairs = [(b,c) for b in B for c in C]
    rng.shuffle(bc_pairs)
    for u,v in bc_pairs[:len(bc_pairs)*3//10]:
        if not has_k4(u,v): adj[u].add(v); adj[v].add(u)

    # A-C: sparse (20%)
    ac_pairs = [(a,c) for a in A for c in C]
    rng.shuffle(ac_pairs)
    for u,v in ac_pairs[:len(ac_pairs)//5]:
        if not has_k4(u,v): adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
