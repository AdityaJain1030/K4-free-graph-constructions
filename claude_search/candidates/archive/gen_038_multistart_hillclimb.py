# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_030_exact_alpha_hillclimb (multi-start: try N different initial orderings, keep best α)
# Hypothesis: best of sqrt(N) different initial orderings reaches α≤6 more reliably at N=33
# Why non-VT: multi-start selects asymmetric solution; final graph has non-uniform neighborhood structure

import random

def _greedy_alpha(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

def _build(N, seed, cap):
    rng = random.Random(seed)
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
    return adj

def construct(N):
    cap = int(N**0.5) + 2
    n_starts = max(3, int(N**0.5) // 2)
    best_adj = None
    best_alpha = N

    # Try multiple structurally different seeds
    seeds = [N * 43 + 11, N * 97 + 23, N * 53 + 7, N * 71 + 37, N * 89 + 53]
    for seed in seeds[:n_starts]:
        adj = _build(N, seed, cap)
        a = _greedy_alpha(adj, N)
        if a < best_alpha:
            best_alpha = a
            best_adj = [s.copy() for s in adj]

    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
