# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (500 seeds at N=30, exact IS selection; target α=7)
# Hypothesis: lucky seed gives K4-free graph on N=30 with α=7 (c=7*7/(30*ln7)=0.839)
# Why non-VT: random regular construction generically non-VT

import random

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
    if N != 30: return []
    target_d = 7
    best_adj = None; best_a = N
    for s in range(500):
        rng = random.Random(N * 19973 + s * 1009)
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
        a = _exact_alpha(adj, N)
        if a < best_a: best_a = a; best_adj = [s.copy() for s in adj]
        if best_a <= 7: break
    if best_adj is None: return []
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
