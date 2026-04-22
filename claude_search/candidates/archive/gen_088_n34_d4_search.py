# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_087_n35_d4_alpha8 (same at N=34; Turán bound α≥7; target α=7 for c=0.577)
# Hypothesis: at N=34, d=4, α=7 gives c=7*4/(34*ln4)=0.587<0.6789
# Why non-VT: random configuration model with K4-removal creates non-uniform degrees

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
    if N < 34 or N > 36: return []
    target_d = 4
    best_adj = None; best_a = N
    for s in range(2000):
        rng = random.Random(N * 70001 + s * 137)
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
        a = _exact_alpha(adj, N)
        if a < best_a: best_a = a; best_adj = [s.copy() for s in adj]
        if best_a <= 7: break
    if best_adj is None: return []
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
