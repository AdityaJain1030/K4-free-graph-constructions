# Family: random_process
# Catalog: ramsey_greedy_triangle_shadow
# Parent: gen_011_ramsey_two_phase (use ER(q) as structured Phase-1 base instead of random triangle-free)
# Hypothesis: structured Phase-1 base (ER(7) at N=57) gives denser K4-free graph with smaller α
# Why non-VT: ER base has two orbits; K4-free extension with seeded order preserves non-VT structure

import random

def construct(N):
    """Use ER(q) as Phase-1 (triangle-free), then K4-free extend."""
    # Find q for ER
    q = None
    for qq in range(2, 20):
        if qq*qq+qq+1 == N and all(qq%d!=0 for d in range(2,qq)):
            q = qq; break

    adj = [set() for _ in range(N)]

    if q:
        p = q
        seen = {}; pts = []
        for x in range(q):
            for y in range(q):
                for z in range(q):
                    if (x,y,z)==(0,0,0): continue
                    if x!=0: iv=pow(x,p-2,p); rep=(1,(y*iv)%p,(z*iv)%p)
                    elif y!=0: iv=pow(y,p-2,p); rep=(0,1,(z*iv)%p)
                    else: rep=(0,0,1)
                    if rep not in seen: seen[rep]=len(pts); pts.append(rep)
        for i in range(N):
            for j in range(i+1,N):
                if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0:
                    adj[i].add(j); adj[j].add(i)
    else:
        # Phase 1: random triangle-free
        rng0 = random.Random(N * 13)
        pairs = [(i,j) for i in range(N) for j in range(i+1,N)]
        rng0.shuffle(pairs)
        def has_tri(u,v): return bool(adj[u]&adj[v])
        for u,v in pairs:
            if not has_tri(u,v): adj[u].add(v); adj[v].add(u)

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    rng = random.Random(N * 7 + 3)
    pairs2 = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(pairs2)
    for u,v in pairs2:
        if not has_k4(u,v): adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
