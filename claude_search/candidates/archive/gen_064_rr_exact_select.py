# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (20 seeds at N≤35, exact IS selection; structural not seed sweep)
# Hypothesis: exact IS selection over 20 structurally different random graphs finds α=7 at N=30
# Why non-VT: random regular with K4 removal; seed diversity gives structurally distinct graphs

import random

def _bb_alpha(adj, N):
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands: best[0] = max(best[0], cur); return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur)
        bb(cands - {v} - adj[v], cur + 1)
    bb(set(range(N)), 0)
    return best[0]

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1

    def build(seed):
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
                                adj[u].discard(v); adj[v].discard(u)
                                changed = True; break
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
        cap = target_d + 1
        for u, v in cands:
            if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
                adj[u].add(v); adj[v].add(u)
        return adj

    num = 20 if N <= 35 else (5 if N <= 50 else 2)
    use_exact = N <= 35
    best_adj = None; best_a = N+1
    for k in range(num):
        adj = build(N * 131 + 47 + k * 3001)
        a = _bb_alpha(adj, N) if use_exact else sum(1 for v in range(N) if len(adj[v]) == 0 or all(w not in adj[v] for w in range(N) if w != v))
        if not use_exact:
            # greedy IS
            deg = [len(adj[i]) for i in range(N)]
            order = sorted(range(N), key=lambda x: deg[x])
            IS = set(); blocked = set()
            for v in order:
                if v not in blocked: IS.add(v); blocked |= adj[v]
            a = len(IS)
        if a < best_a: best_a = a; best_adj = adj
    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
