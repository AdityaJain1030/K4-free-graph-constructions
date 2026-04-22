# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (simulated annealing edge swaps to minimize greedy α)
# Hypothesis: SA on edge set with greedy-IS objective reduces α below RR baseline
# Why non-VT: SA destroys regularity; each random path creates unique orbit structure

import random

def _greedy_is(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked:
            IS.add(v); blocked |= adj[v]
    return len(IS)

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
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
                common = list(adj[u] & adj[v])
                for a in range(len(common)):
                    for b in range(a+1, len(common)):
                        if common[b] in adj[common[a]]:
                            adj[u].discard(v); adj[v].discard(u)
                            changed = True; break
                    if changed: break
                if changed: break
            if changed: break

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Re-saturate
    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    # SA phase: swap edges to minimize greedy IS (only at small N for speed)
    if N <= 60:
        cur_alpha = _greedy_is(adj, N)
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
        for _ in range(150):
            if not edges or not non_edges: break
            e_rem = rng.choice(edges)
            e_add = rng.choice(non_edges)
            u1, v1 = e_rem; u2, v2 = e_add
            if u2 == v2 or v2 in adj[u2]: continue
            adj[u1].discard(v1); adj[v1].discard(u1)
            if not has_k4(u2, v2):
                adj[u2].add(v2); adj[v2].add(u2)
                new_alpha = _greedy_is(adj, N)
                if new_alpha <= cur_alpha:
                    cur_alpha = new_alpha
                    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
                    non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
                else:
                    adj[u2].discard(v2); adj[v2].discard(u2)
                    adj[u1].add(v1); adj[v1].add(u1)
            else:
                adj[u1].add(v1); adj[v1].add(u1)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
