# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_047_rr_maxK4_removal (multi-seed search at N=35 target, pick best exact-α)
# Hypothesis: R(4,6)=36 guarantees K4-free α=5 at N=35 exists; multi-seed + exact IS finds it
# Why non-VT: random regular + asymmetric K4 removal gives non-transitive Aut

import random
from collections import defaultdict

def _exact_alpha(adj, N, limit=6):
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands:
            if cur > best[0]: best[0] = cur
            return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur)
        bb(cands - {v} - adj[v], cur + 1)
    bb(set(range(N)), 0)
    return best[0]

def _build(N, seed):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(seed)
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
    return adj

def construct(N):
    # Only multi-seed at small N for speed
    num_seeds = 6 if N <= 40 else 2
    best_adj = None; best_a = N+1
    for k in range(num_seeds):
        adj = _build(N, N * 101 + 61 + k * 1009)
        a = _exact_alpha(adj, N) if N <= 40 else sum(len(adj[v]) for v in range(N))
        if a < best_a:
            best_a = a; best_adj = adj
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
