# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_030_exact_alpha_hillclimb (simulated annealing to escape α=9 local minimum)
# Hypothesis: SA with T=2.0→0.1 allows uphill IS moves to find α≤6 at N=32-35 within 5s
# Why non-VT: SA-modified graph inherits non-uniform degree structure from random initialization

import random, math

def _greedy_alpha(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

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

    # Simulated annealing: edge swaps, accept worse with Boltzmann probability
    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
    all_pairs = [(i,j) for i in range(N) for j in range(i+1,N)]
    cur_alpha = _greedy_alpha(adj, N)
    T = 3.0

    for step in range(400):
        T = 3.0 * (0.995 ** step)
        e = edges[rng.randint(0, len(edges)-1)]
        u, v = e
        # Try a random non-edge
        a = rng.randint(0, N-1)
        b = rng.randint(0, N-1)
        if a == b or b in adj[a] or len(adj[a]) >= cap or len(adj[b]) >= cap: continue
        if has_k4(a, b): continue
        # Swap e -> (a,b)
        adj[u].discard(v); adj[v].discard(u)
        adj[a].add(b); adj[b].add(a)
        new_alpha = _greedy_alpha(adj, N)
        delta = new_alpha - cur_alpha
        if delta < 0 or rng.random() < math.exp(-delta / max(T, 0.01)):
            edges.remove(e); edges.append((min(a,b), max(a,b)))
            cur_alpha = new_alpha
        else:
            adj[u].add(v); adj[v].add(u)
            adj[a].discard(b); adj[b].discard(a)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
