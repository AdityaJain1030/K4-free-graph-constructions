# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_095_rr_d4_n30 (target_d=3, re-saturate to cap=4; test all N)
# Hypothesis: K4-free 3-regular + saturation gives d_max=4 with lower α at large N
# Why non-VT: random configuration model generically non-VT

import random

def construct(N):
    target_d = 3
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 101 + 61)
    stubs = []
    for v in range(N): stubs.extend([v] * target_d)
    rng.shuffle(stubs)
    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs), 2):
        if i+1 < len(stubs):
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

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    for u, v in cands:
        if len(adj[u]) <= target_d and len(adj[v]) <= target_d and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
