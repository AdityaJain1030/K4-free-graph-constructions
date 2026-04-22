# Family: crossover
# Catalog: asymmetric_lift_generic
# Parent: gen_008_er_polarity + gen_013_bohman_keevash (2-layer ER base, greedy K4-free cross-edges)
# Hypothesis: 2-layer ER(5) at N=62 with greedy K4-free cross-edges should give d_max~10, α~10
# Why non-VT: ER base has two orbits; non-uniform cross-edges between layers break layer symmetry

import random

def _er_edges(q):
    p = q
    seen = {}
    pts = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z) == (0,0,0): continue
                if x != 0: iv=pow(x,p-2,p); rep=(1,(y*iv)%p,(z*iv)%p)
                elif y != 0: iv=pow(y,p-2,p); rep=(0,1,(z*iv)%p)
                else: rep=(0,0,1)
                if rep not in seen: seen[rep]=len(pts); pts.append(rep)
    edges=[]
    n=len(pts)
    for i in range(n):
        for j in range(i+1,n):
            if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0:
                edges.append((i,j))
    return n, edges

def construct(N):
    q = 5
    m, base_edges = _er_edges(q)
    k = N // m
    if k < 2 or k * m != N:
        # Try q=7
        q2 = 7
        m2, be2 = _er_edges(q2)
        k2 = N // m2
        if k2 >= 2 and k2 * m2 == N:
            m, base_edges, k = m2, be2, k2
        else:
            return []

    total = k * m
    adj = [set() for _ in range(total)]
    for layer in range(k):
        off = layer * m
        for u, v in base_edges:
            adj[off+u].add(off+v); adj[off+v].add(off+u)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Greedy K4-free cross-edges between adjacent layers, seeded
    rng = random.Random(N * 23 + 11)
    cross_candidates = []
    for layer in range(k):
        next_l = (layer + 1) % k
        off_a, off_b = layer * m, next_l * m
        pairs = [(off_a+u, off_b+v) for u in range(m) for v in range(m)]
        rng.shuffle(pairs)
        cross_candidates.extend(pairs[:m*2])  # limit candidates per layer pair

    rng.shuffle(cross_candidates)
    for u, v in cross_candidates:
        if v not in adj[u] and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(total) for v in adj[u] if v > u]
