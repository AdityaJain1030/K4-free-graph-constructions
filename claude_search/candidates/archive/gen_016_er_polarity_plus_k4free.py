# Family: polarity
# Catalog: er_polarity
# Parent: gen_008_er_polarity (extend ER(q) base by greedily adding K4-free edges to reduce α)
# Hypothesis: K4-free extension of ER(7) at N=57 increases d_max and reduces independent sets
# Why non-VT: ER(q) base has two orbits; K4-free extension with seeded order preserves asymmetry

import random

def construct(N):
    q = None
    for qq in range(2, 200):
        if qq*qq + qq + 1 == N and all(qq % d != 0 for d in range(2, qq)):
            q = qq
            break
    if q is None:
        return []
    p = q

    seen = {}
    pts = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z) == (0,0,0): continue
                if x != 0:
                    iv = pow(x,p-2,p); rep = (1,(y*iv)%p,(z*iv)%p)
                elif y != 0:
                    iv = pow(y,p-2,p); rep = (0,1,(z*iv)%p)
                else:
                    rep = (0,0,1)
                if rep not in seen:
                    seen[rep] = len(pts); pts.append(rep)

    adj = [set() for _ in range(N)]
    for i in range(N):
        for j in range(i+1, N):
            if sum(pts[i][k]*pts[j][k] for k in range(3)) % p == 0:
                adj[i].add(j); adj[j].add(i)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]:
                    return True
        return False

    rng = random.Random(N * 19 + 5)
    candidates = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(candidates)
    for u, v in candidates:
        if not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
