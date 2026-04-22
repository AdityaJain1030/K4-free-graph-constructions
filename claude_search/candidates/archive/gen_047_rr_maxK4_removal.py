# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (remove max-K4-participation edge first, not first-found)
# Hypothesis: smarter K4 removal (edge in most K4s removed first) leaves denser K4-free residual
# Why non-VT: asymmetric K4 removal creates vertex-degree variation → non-transitive Aut

import random
from collections import defaultdict

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 101 + 61)

    stubs = []
    for v in range(N): stubs.extend([v] * target_d)
    rng.shuffle(stubs)
    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs)-1, 2):
        u, v = stubs[i], stubs[i+1]
        if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)

    # Remove edges: find K4s, remove edge with max K4 participation
    while True:
        k4_count = defaultdict(int)
        found_k4 = False
        for u in range(N):
            for v in adj[u]:
                if v <= u: continue
                for w in adj[u] & adj[v]:
                    if w <= v: continue
                    for x in adj[u] & adj[v] & adj[w]:
                        if x <= w: continue
                        found_k4 = True
                        for e in [(min(u,v),max(u,v)),(min(u,w),max(u,w)),(min(u,x),max(u,x)),
                                  (min(v,w),max(v,w)),(min(v,x),max(v,x)),(min(w,x),max(w,x))]:
                            k4_count[e] += 1
        if not found_k4: break
        worst = max(k4_count, key=k4_count.get)
        adj[worst[0]].discard(worst[1]); adj[worst[1]].discard(worst[0])

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
