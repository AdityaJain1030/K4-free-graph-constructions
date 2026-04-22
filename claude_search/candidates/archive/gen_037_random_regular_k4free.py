# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_036_exact_IS_targeted (start from random regular graph, remove K4 edges, re-saturate)
# Hypothesis: random d-regular starting point may have smaller α than greedy-built graph at same d
# Why non-VT: random regular graph plus K4 fixing destroys regularity → vertex-inhomogeneous degrees

import random

def construct(N):
    target_d = int(N**0.5) + 1  # target degree
    if target_d * N % 2 != 0:
        target_d += 1
    rng = random.Random(N * 101 + 61)

    # Build random regular graph via configuration model
    stubs = []
    for v in range(N):
        stubs.extend([v] * target_d)
    rng.shuffle(stubs)

    adj = [set() for _ in range(N)]
    # Pair stubs
    for i in range(0, len(stubs), 2):
        if i+1 < len(stubs):
            u, v = stubs[i], stubs[i+1]
            if u != v and v not in adj[u]:
                adj[u].add(v); adj[v].add(u)

    # Remove edges creating K4
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
                            # K4 found: remove edge (u,v)
                            adj[u].discard(v); adj[v].discard(u)
                            changed = True
                            break
                    if changed: break
                if changed: break
            if changed: break

    # Add K4-free edges greedily
    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    candidates = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(candidates)
    for u, v in candidates:
        if len(adj[u]) <= target_d and len(adj[v]) <= target_d and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
