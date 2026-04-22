# Family: random_process
# Catalog: bohman_keevash_k4_process
# Parent: gen_026_bohman_degree_cap (adversarial ordering: prioritize edges that shrink current max IS)
# Hypothesis: greedily connecting independent-set vertices reduces α at the cost of K4 constraints
# Why non-VT: greedy IS-shrinking order is vertex-inhomogeneous → no transitive automorphism

import random

def _greedy_IS(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    indep = set(); blocked = set()
    for v in order:
        if v not in blocked:
            indep.add(v); blocked |= adj[v]
    return indep

def construct(N):
    cap = int(N**0.5) + 2
    adj = [set() for _ in range(N)]
    rng = random.Random(N * 67 + 31)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    for _ in range(N * 20):
        IS = list(_greedy_IS(adj, N))
        if len(IS) < 2:
            break
        # Pick two IS vertices and try to connect them
        rng.shuffle(IS)
        connected = False
        for i in range(min(10, len(IS))):
            for j in range(i+1, min(10, len(IS))):
                u, v = IS[i], IS[j]
                if v not in adj[u] and len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
                    adj[u].add(v); adj[v].add(u)
                    connected = True
                    break
            if connected: break
        if not connected:
            # Fall back to random edge
            a, b = rng.randint(0, N-1), rng.randint(0, N-1)
            if a != b and b not in adj[a] and len(adj[a]) < cap and len(adj[b]) < cap and not has_k4(a, b):
                adj[a].add(b); adj[b].add(a)

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
