# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_047_rr_maxK4_removal (SA with exact IS objective at N≤35 only)
# Hypothesis: exact IS scoring in SA (not greedy proxy) finds α=6 at N=35 for c≈0.88
# Why non-VT: SA destroys regularity and all symmetry; final graph depends on random walk path

import random
from collections import defaultdict

def _exact_alpha(adj, N):
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

    # SA with exact IS — only at small N
    if N <= 35:
        cur_a = _exact_alpha(adj, N)
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
        for _ in range(50):
            if cur_a <= 5: break
            if not edges or not non_edges: break
            e_rem = rng.choice(edges)
            e_add = rng.choice(non_edges)
            u1, v1 = e_rem; u2, v2 = e_add
            if v2 in adj[u2]: continue
            adj[u1].discard(v1); adj[v1].discard(u1)
            if not has_k4(u2, v2):
                adj[u2].add(v2); adj[v2].add(u2)
                new_a = _exact_alpha(adj, N)
                if new_a <= cur_a:
                    cur_a = new_a
                    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
                    non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
                else:
                    adj[u2].discard(v2); adj[v2].discard(u2)
                    adj[u1].add(v1); adj[v1].add(u1)
            else:
                adj[u1].add(v1); adj[v1].add(u1)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
