# Family: polarity
# Catalog: er_polarity_delete_matching
# Parent: gen_008_er_polarity (add greedy edges to ER polarity to increase d_max, lower c)
# Hypothesis: ER polarity is C4-free; adding K4-free edges increases d_max faster than α
# Why non-VT: absolute/non-absolute orbit split in ER plus new random edges breaks transitivity

import random

def construct(N):
    q = None
    for qq in range(2, 200):
        if qq*qq + qq + 1 == N and all(qq % d != 0 for d in range(2, max(2,qq))):
            q = qq; break
    if q is None: return []

    pts = []
    for a in range(q):
        for b in range(q):
            pts.append((1, a, b))
    for b in range(q):
        pts.append((0, 1, b))
    pts.append((0, 0, 1))

    def dot(p1, p2):
        return (p1[0]*p2[0] + p1[1]*p2[1] + p1[2]*p2[2]) % q

    adj = [set() for _ in range(N)]
    for i in range(N):
        for j in range(i+1, N):
            if dot(pts[i], pts[j]) == 0:
                adj[i].add(j); adj[j].add(i)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Add more K4-free edges (ER is C4-free so dense but K4-free)
    rng = random.Random(N * 211 + 79)
    non_edges = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(non_edges)
    cap = q + 3
    for u, v in non_edges:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
