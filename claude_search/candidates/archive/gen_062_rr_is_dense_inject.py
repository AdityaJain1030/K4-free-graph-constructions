# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_061_is_edge_injection (inject ALL valid K4-free edges within max IS at once)
# Hypothesis: injecting all IS-internal K4-free edges at once reduces α more aggressively
# Why non-VT: IS-guided saturation creates unique non-regular degree structure

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

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    # Iterative IS injection: add all K4-free edges within greedy IS
    for _ in range(30):
        deg = [len(adj[i]) for i in range(N)]
        order = sorted(range(N), key=lambda x: deg[x])
        IS = set(); blocked = set()
        for v in order:
            if v not in blocked:
                IS.add(v); blocked |= adj[v]
        IS_list = list(IS)
        any_added = False
        for i in range(len(IS_list)):
            for j in range(i+1, len(IS_list)):
                u, v = IS_list[i], IS_list[j]
                if not has_k4(u, v):
                    adj[u].add(v); adj[v].add(u)
                    any_added = True
        if not any_added: break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
