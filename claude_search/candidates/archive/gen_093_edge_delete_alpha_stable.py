# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (delete edges while keeping α constant; reduce d_max)
# Hypothesis: many edges in gen_037 N=30 graph are IS-irrelevant; removing them drops d_max→4 at α=8
# Why non-VT: original non-VT; edge deletion makes it more irregular

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
    # Recreate gen_037 N=30 graph
    target_d = 7
    rng = random.Random(N * 101 + 61)
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

    cur_a = _exact_alpha(adj, N)

    # Greedily delete edges while keeping α constant
    rng2 = random.Random(N * 997 + 13)
    improved = True
    while improved:
        improved = False
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        rng2.shuffle(edges)
        for u, v in edges:
            adj[u].discard(v); adj[v].discard(u)
            new_a = _exact_alpha(adj, N)
            if new_a == cur_a:
                improved = True  # Keep deletion, restart scan
                break
            else:
                adj[u].add(v); adj[v].add(u)  # Undo

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
