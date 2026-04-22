# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: gen_018_er_lift_k4free_crossover (add ALL K4-safe cross-edges, not just hash-selected subset)
# Hypothesis: maximal K4-free cross-edges between 2 ER(5) layers at N=62 minimizes α relative to d_max
# Why non-VT: ER base non-VT; greedy ordering of cross-edges creates asymmetric cross-structure

import random

def _er_adj(q, total_n):
    p=q; seen={}; pts=[]
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z)==(0,0,0): continue
                if x!=0: iv=pow(x,p-2,p); rep=(1,(y*iv)%p,(z*iv)%p)
                elif y!=0: iv=pow(y,p-2,p); rep=(0,1,(z*iv)%p)
                else: rep=(0,0,1)
                if rep not in seen: seen[rep]=len(pts); pts.append(rep)
    adj=[set() for _ in range(total_n)]
    m=len(pts)
    for i in range(m):
        for j in range(i+1,m):
            if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0:
                adj[i].add(j); adj[j].add(i)
    return m, adj

def construct(N):
    q=5; m, adj = _er_adj(q, N)
    k=N//m
    if k<2 or k*m!=N:
        q=7; m,adj=_er_adj(q,N); k=N//m
        if k<2 or k*m!=N: return []
    # Re-build with correct total size
    m2,adj2=_er_adj(q, k*m)
    for layer in range(1,k):
        off=layer*m
        for u,v in [(u,v) for u in range(m) for v in adj2[u] if v<m and v>u]:
            adj2[off+u].add(off+v); adj2[off+v].add(off+u)
    adj=adj2; total=k*m

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    rng=random.Random(N*61+23)
    for layer in range(k):
        nl=(layer+1)%k; oa,ob=layer*m,nl*m
        pairs=[(oa+u,ob+v) for u in range(m) for v in range(m)]
        rng.shuffle(pairs)
        for u,v in pairs:
            if v not in adj[u] and not has_k4(u,v):
                adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(total) for v in adj[u] if v>u]
