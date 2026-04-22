# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (add re-saturation edges in min-degree order instead of random)
# Hypothesis: preferring low-degree vertices in re-saturation creates more uniform graph with smaller α
# Why non-VT: min-degree ordering in re-saturation creates edge distribution without cyclic symmetry

import random

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

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

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
                            adj[u].discard(v); adj[v].discard(u); changed = True; break
                    if changed: break
                if changed: break
            if changed: break

    # Re-saturate in ascending min-degree order
    cap = target_d + 1
    changed = True
    while changed:
        changed = False
        best = None; best_deg = cap + 1
        for u in range(N):
            if len(adj[u]) >= cap: continue
            for v in range(u+1, N):
                if v in adj[u] or len(adj[v]) >= cap: continue
                if not has_k4(u, v):
                    d = min(len(adj[u]), len(adj[v]))
                    if d < best_deg:
                        best_deg = d; best = (u, v)
        if best:
            u, v = best
            adj[u].add(v); adj[v].add(u)
            changed = True

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
