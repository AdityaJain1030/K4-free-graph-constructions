# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (target d=5 at N=50-100; c=α*5/(N*ln5) may be lower for moderate N)
# Hypothesis: d=5-regular K4-free at N=60-80 gives c < 0.96 if α/N < 0.37
# Why non-VT: configuration model destroys symmetry; K4-removal creates degree irregularity

import random

def construct(N):
    target_d = 5
    rng = random.Random(N * 1031 + 179)
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

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    # Re-saturate up to cap=6
    non_edges = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(non_edges)
    for u, v in non_edges:
        if len(adj[u]) <= 5 and len(adj[v]) <= 5 and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
