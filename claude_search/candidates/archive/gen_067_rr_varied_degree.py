# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (use N-dependent optimal degree target 2*sqrt(N))
# Hypothesis: higher degree target 2*sqrt(N) with aggressive K4 removal gives better alpha/dmax tradeoff
# Why non-VT: varied degree post-K4-removal creates non-uniform structure

import random
from collections import defaultdict

def construct(N):
    target_d = 2 * int(N**0.5)
    if target_d * N % 2 != 0: target_d += 1
    if target_d < 4: target_d = 4
    rng = random.Random(N * 101 + 61)

    stubs = []
    for v in range(N): stubs.extend([v] * target_d)
    rng.shuffle(stubs)
    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs)-1, 2):
        u, v = stubs[i], stubs[i+1]
        if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)

    while True:
        k4c = defaultdict(int); found = False
        for u in range(N):
            for v in adj[u]:
                if v <= u: continue
                for w in adj[u] & adj[v]:
                    if w <= v: continue
                    for x in adj[u] & adj[v] & adj[w]:
                        if x <= w: continue
                        found = True
                        for e in [(min(u,v),max(u,v)),(min(u,w),max(u,w)),(min(u,x),max(u,x)),
                                  (min(v,w),max(v,w)),(min(v,x),max(v,x)),(min(w,x),max(w,x))]:
                            k4c[e] += 1
        if not found: break
        worst = max(k4c, key=k4c.get)
        adj[worst[0]].discard(worst[1]); adj[worst[1]].discard(worst[0])

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = int(N**0.5) + 2
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
