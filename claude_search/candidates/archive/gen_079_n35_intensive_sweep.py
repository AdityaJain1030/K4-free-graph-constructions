# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_064_rr_exact_select (300 seeds at N=35-40, greedy IS → exact IS for top candidates)
# Hypothesis: c=α*6/(35*ln6) < 0.679 if α=7; need 300 seeds to find a 6-regular K4-free with α=7
# Why non-VT: random stub-matching construction destroys symmetry generically

import random
import math

def _build(N, seed):
    target_d = 6
    rng = random.Random(seed)
    stubs = []
    for v in range(N): stubs.extend([v] * target_d)
    rng.shuffle(stubs)
    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs)-1, 2):
        u, v = stubs[i], stubs[i+1]
        if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)
    # K4 removal
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

def construct(N):
    if N < 34 or N > 42: return []
    best_a = N; best_adj = None
    for s in range(150):
        adj = _build(N, N * 7001 + s * 997)
        dm = max(len(adj[v]) for v in range(N))
        if dm < 2: continue
        a = _greedy_is(adj, N)
        if a < best_a: best_a = a; best_adj = adj
    if best_adj is None: return []
    # Exact check on best
    exact = _exact_alpha(best_adj, N)
    dm = max(len(best_adj[v]) for v in range(N))
    if dm >= 2 and exact * dm / (N * math.log(dm)) < 0.9:
        return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
