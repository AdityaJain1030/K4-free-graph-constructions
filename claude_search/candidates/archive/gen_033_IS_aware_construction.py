# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_032_targeted_IS_attack (build graph by prioritizing IS-breaking edges from the start)
# Hypothesis: inserting IS-breaking edges first (before degree cap fills) gives smaller final α
# Why non-VT: IS-targeted ordering creates asymmetric vertex neighborhoods

import random

def construct(N):
    cap = int(N**0.5) + 2
    rng = random.Random(N * 89 + 53)
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    def greedy_IS():
        deg = [len(adj[i]) for i in range(N)]
        order = sorted(range(N), key=lambda x: deg[x])
        IS = set(); blocked = set()
        for v in order:
            if v not in blocked: IS.add(v); blocked |= adj[v]
        return IS

    # Iteratively build graph by attacking current IS
    for _ in range(N * cap):
        IS = list(greedy_IS())
        if len(IS) <= cap // 2: break
        rng.shuffle(IS)
        added = False
        for i in range(len(IS)):
            for j in range(i+1, len(IS)):
                u, v = IS[i], IS[j]
                if v not in adj[u] and len(adj[u]) < cap and len(adj[v]) < cap:
                    if not has_k4(u, v):
                        adj[u].add(v); adj[v].add(u)
                        added = True; break
            if added: break
        if not added:
            # No IS-connecting edges available; add random K4-free edge
            all_ne = [(i,j) for i in range(N) for j in range(i+1,N)
                      if j not in adj[i] and len(adj[i])<cap and len(adj[j])<cap]
            if not all_ne: break
            rng.shuffle(all_ne)
            for u, v in all_ne[:10]:
                if not has_k4(u, v):
                    adj[u].add(v); adj[v].add(u); break
            else:
                break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
