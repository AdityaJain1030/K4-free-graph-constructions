# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (different hash seed: N*157+83 instead of N*101+61)
# Hypothesis: alternative RR realization may achieve α≤7 at some N in [30,35] giving c≤0.87
# Why non-VT: RR construction with different pairing creates distinct vertex-degree structure

import random

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 157 + 83)  # different structural seed

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

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
