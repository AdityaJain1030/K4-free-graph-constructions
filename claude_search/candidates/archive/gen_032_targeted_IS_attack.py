# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_030_exact_alpha_hillclimb (targeted attack: find exact IS, connect its members K4-free)
# Hypothesis: connecting IS members directly (not random swaps) reduces α faster toward ≤6 at N=33
# Why non-VT: IS-targeted edge insertion creates structurally distinct high/low-degree vertices

import random

def _find_IS(adj, N):
    """Find a large independent set via greedy+local."""
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked:
            IS.add(v); blocked |= adj[v]
    return IS

def construct(N):
    cap = int(N**0.5) + 2
    rng = random.Random(N * 43 + 11)
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    pairs = [(i,j) for i in range(N) for j in range(i+1,N)]
    rng.shuffle(pairs)
    for u, v in pairs:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    # Phase 2: targeted IS attack - repeatedly find IS, connect pairs
    for _ in range(300):
        IS = list(_find_IS(adj, N))
        if len(IS) <= 5: break
        # Try to connect pairs of IS vertices
        rng.shuffle(IS)
        connected = False
        for i in range(len(IS)):
            for j in range(i+1, len(IS)):
                u, v = IS[i], IS[j]
                if v not in adj[u] and len(adj[u]) < cap and len(adj[v]) < cap:
                    if not has_k4(u, v):
                        adj[u].add(v); adj[v].add(u)
                        connected = True
                        break
            if connected: break
        if not connected: break

    # Phase 3: add any remaining K4-free edges
    remaining = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]
                 and len(adj[i]) < cap and len(adj[j]) < cap]
    rng.shuffle(remaining)
    for u, v in remaining:
        if not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
