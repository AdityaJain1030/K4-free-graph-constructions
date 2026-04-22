# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: gen_010_asymmetric_lift (use ER(7) base at N=57, 2 layers → N=114 for Stage 2)
# Hypothesis: 2-layer ER(7) at N=114 with hash cross-edges reduces α/N below single-layer baseline
# Why non-VT: ER base has two orbits; non-uniform cross-edges preserve non-VT structure

import random

def _er_edges(q):
    p=q; seen={}; pts=[]
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z)==(0,0,0): continue
                if x!=0: iv=pow(x,p-2,p); rep=(1,(y*iv)%p,(z*iv)%p)
                elif y!=0: iv=pow(y,p-2,p); rep=(0,1,(z*iv)%p)
                else: rep=(0,0,1)
                if rep not in seen: seen[rep]=len(pts); pts.append(rep)
    e=[]
    n=len(pts)
    for i in range(n):
        for j in range(i+1,n):
            if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0: e.append((i,j))
    return n,e

def construct(N):
    q=7; m,be=_er_edges(q)
    k=N//m
    if k<2 or k*m!=N:
        q=5; m,be=_er_edges(q); k=N//m
        if k<2 or k*m!=N: return []

    total=k*m
    adj=[set() for _ in range(total)]
    for layer in range(k):
        off=layer*m
        for u,v in be:
            adj[off+u].add(off+v); adj[off+v].add(off+u)

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    rng=random.Random(N*29+17)
    for layer in range(k):
        nl=(layer+1)%k; oa,ob=layer*m,nl*m
        pairs=[(oa+u,ob+v) for u in range(m) for v in range(m) if (u*13+v*7+layer*97)%7==0]
        rng.shuffle(pairs)
        for u,v in pairs:
            if v not in adj[u] and not has_k4(u,v):
                adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(total) for v in adj[u] if v>u]
