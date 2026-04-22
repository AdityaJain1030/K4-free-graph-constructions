# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_088_n34_d4_search (greedy IS for 1000 seeds, exact IS for top-3; avoids timeout)
# Hypothesis: greedy IS proxies well for seed selection; top-1 by greedy at N=35 may have α≤9
# Why non-VT: random configuration model generically non-VT

import random

def _greedy_is(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

def _exact_alpha(adj, N):
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands: best[0] = max(best[0], cur); return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur); bb(cands - {v} - adj[v], cur+1)
    bb(set(range(N)), 0)
    return best[0]

def _build(N, seed, target_d=4):
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
                cm = list(adj[u] & adj[v])
                for a in range(len(cm)):
                    for b in range(a+1, len(cm)):
                        if cm[b] in adj[cm[a]]:
                            adj[u].discard(v); adj[v].discard(u); changed=True; break
                    if changed: break
                if changed: break
            if changed: break
    return adj

def construct(N):
    if N < 34 or N > 36: return []
    top3 = []  # (greedy_IS, adj)
    for s in range(1000):
        adj = _build(N, N * 99991 + s * 3)
        dm = max(len(adj[v]) for v in range(N))
        if dm < 2: continue
        g = _greedy_is(adj, N)
        top3.append((g, adj))
        top3.sort(key=lambda x: x[0])
        top3 = top3[:3]
    if not top3: return []
    # Exact IS for top-3
    best_adj = None; best_a = N
    for _, adj in top3:
        a = _exact_alpha(adj, N)
        if a < best_a: best_a = a; best_adj = adj
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
