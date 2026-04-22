# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_080_sa_exact_n35 (SA with greedy IS proxy; 3000 steps; restart from best)
# Hypothesis: greedy-IS-guided SA at N=35 with 3000 steps finds α≤9 improving on gen_079 α=12
# Why non-VT: SA perturbations on random regular base break all symmetry

import random

def _greedy_is(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

def _has_k4(adj, u, v):
    cm = list(adj[u] & adj[v])
    for a in range(len(cm)):
        for b in range(a+1, len(cm)):
            if cm[b] in adj[cm[a]]: return True
    return False

def construct(N):
    if N < 34 or N > 50: return []
    rng = random.Random(N * 78901 + 31)
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
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

    cur_a = _greedy_is(adj, N); best_adj = [s.copy() for s in adj]; best_a = cur_a
    T = 1.5
    for step in range(3000):
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
        if not edges or not non_edges: break
        u1,v1 = rng.choice(edges); u2,v2 = rng.choice(non_edges)
        adj[u1].discard(v1); adj[v1].discard(u1)
        if not _has_k4(adj, u2, v2):
            adj[u2].add(v2); adj[v2].add(u2)
            new_a = _greedy_is(adj, N)
            import math
            if new_a < cur_a or rng.random() < math.exp(-(new_a-cur_a)/max(T,0.01)):
                cur_a = new_a
                if cur_a < best_a: best_a = cur_a; best_adj = [s.copy() for s in adj]
            else:
                adj[u2].discard(v2); adj[v2].discard(u2)
                adj[u1].add(v1); adj[v1].add(u1)
        else:
            adj[u1].add(v1); adj[v1].add(u1)
        T *= 0.999

    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
