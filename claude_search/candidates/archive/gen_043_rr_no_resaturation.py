# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (skip re-saturation; keep RR graph after K4 removal only)
# Hypothesis: removing the re-saturation step preserves the RR structural balance that gives small α
# Why non-VT: random regular graph with K4 edges removed has non-uniform degrees → non-transitive Aut

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

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
