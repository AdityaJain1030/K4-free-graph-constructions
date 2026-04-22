# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (50 random seeds at N≤38, pick min greedy-α)
# Hypothesis: large seed sweep finds rare low-α instances (α=6 or 7 at N=30)
# Why non-VT: random regular + K4 removal; different seeds give structurally different graphs

import random

def _greedy_is(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1

    def build(seed):
        rng = random.Random(seed)
        stubs = []
        for v in range(N): stubs.extend([v] * target_d)
        rng.shuffle(stubs)
        adj = [set() for _ in range(N)]
        for i in range(0, len(stubs)-1, 2):
            u, v = stubs[i], stubs[i+1]
            if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)
        changed = True
        while changed:
            changed = False
            for u in range(N):
                for v in list(adj[u]):
                    if v <= u: continue
                    c2 = list(adj[u] & adj[v])
                    for a in range(len(c2)):
                        for b in range(a+1, len(c2)):
                            if c2[b] in adj[c2[a]]:
                                adj[u].discard(v); adj[v].discard(u)
                                changed = True; break
                        if changed: break
                    if changed: break
                if changed: break
        def has_k4(u, v):
            c2 = list(adj[u] & adj[v])
            for a in range(len(c2)):
                for b in range(a+1, len(c2)):
                    if c2[b] in adj[c2[a]]: return True
            return False
        cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
        rng.shuffle(cands)
        cap = target_d + 1
        for u, v in cands:
            if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
                adj[u].add(v); adj[v].add(u)
        return adj

    num = 30 if N <= 38 else (10 if N <= 60 else 3)
    best_adj = None; best_a = N+1
    for k in range(num):
        adj = build(N * 101 + 61 + k * 2003)
        a = _greedy_is(adj, N)
        if a < best_a: best_a = a; best_adj = adj
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
