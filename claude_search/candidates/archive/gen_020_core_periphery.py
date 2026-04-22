# Family: core_periphery
# Catalog: asymmetric_lift_generic
# Parent: none (fresh non-VT design: dense K4-free core + sparse periphery)
# Hypothesis: dense ER(5) core (31 vertices) + periphery vertices connected to core via K4-free rule
# Why non-VT: core vertices have degree ~6, periphery vertices have smaller degree; two distinct orbits

import random

def construct(N):
    """Core-periphery: ER(5) core on 31 vertices, extra N-31 vertices as periphery."""
    q = 5; p = q; m = q*q+q+1
    if N < m: return []

    seen = {}; pts = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z)==(0,0,0): continue
                if x!=0: iv=pow(x,p-2,p); rep=(1,(y*iv)%p,(z*iv)%p)
                elif y!=0: iv=pow(y,p-2,p); rep=(0,1,(z*iv)%p)
                else: rep=(0,0,1)
                if rep not in seen: seen[rep]=len(pts); pts.append(rep)

    adj = [set() for _ in range(N)]
    for i in range(m):
        for j in range(i+1,m):
            if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0:
                adj[i].add(j); adj[j].add(i)

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    rng = random.Random(N * 41 + 13)
    for pv in range(m, N):
        core_nbrs = list(range(m))
        rng.shuffle(core_nbrs)
        count = 0
        for cv in core_nbrs:
            if count >= 3: break
            if not has_k4(pv, cv):
                adj[pv].add(cv); adj[cv].add(pv); count += 1

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
