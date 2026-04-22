# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_093_edge_delete_alpha_stable (fixed: use gen_037 base exactly; target_d=sqrt(N)+1)
# Hypothesis: gen_037(N=30) has α=8, d=7; deleting IS-irrelevant edges brings d→5, c→0.894
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
    target_d = int(N**0.5) + 1
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

    cur_a = _exact_alpha(adj, N)
    rng2 = random.Random(N * 1013 + 7)
    improved = True
    while improved:
        improved = False
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        rng2.shuffle(edges)
        for u, v in edges:
            adj[u].discard(v); adj[v].discard(u)
            new_a = _exact_alpha(adj, N)
            if new_a <= cur_a:
                cur_a = new_a; improved = True; break
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
