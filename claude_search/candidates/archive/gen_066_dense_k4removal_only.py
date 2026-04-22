# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (denser start d=sqrt(N)+3, K4 removal only, no re-saturation)
# Hypothesis: denser RR start leaves denser K4-free residual with better alpha after K4 removal
# Why non-VT: K4 removal from a denser irregular initial graph creates non-uniform degrees

import random
from collections import defaultdict

def construct(N):
    target_d = int(N**0.5) + 3
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 101 + 61)

    stubs = []
    for v in range(N): stubs.extend([v] * target_d)
    rng.shuffle(stubs)
    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs)-1, 2):
        u, v = stubs[i], stubs[i+1]
        if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)

    # Max-K4-participation removal
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

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
