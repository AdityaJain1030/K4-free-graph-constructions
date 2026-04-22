# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (d=7 at N=35; target α=9,d=7 → c=9*7/(35*ln7)=0.925)
# Hypothesis: at N=35 d=7, lucky seed achieves α=9 (c=0.925 < 0.9593 gen_037 best)
# Why non-VT: random regular construction generically non-VT

import random

def _greedy_is(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

def construct(N):
    if N < 34 or N > 40: return []
    target_d = 7
    best_adj = None; best_a = N
    for s in range(500):
        rng = random.Random(N * 131071 + s * 293)
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
                    cm = list(adj[u] & adj[v])
                    for a in range(len(cm)):
                        for b in range(a+1, len(cm)):
                            if cm[b] in adj[cm[a]]:
                                adj[u].discard(v); adj[v].discard(u); changed=True; break
                        if changed: break
                    if changed: break
                if changed: break
        dm = max(len(adj[v]) for v in range(N))
        if dm < 2: continue
        a = _greedy_is(adj, N)
        if a < best_a: best_a = a; best_adj = [s.copy() for s in adj]
    if best_adj is None: return []
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
