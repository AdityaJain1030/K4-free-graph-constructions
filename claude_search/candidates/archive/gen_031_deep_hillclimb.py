# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_030_exact_alpha_hillclimb (2000 iterations, larger neighborhood, targets N=30-40)
# Hypothesis: more hill-climbing iterations can reduce α from 9 to ≤6 at N=33, giving c<0.6789
# Why non-VT: seeded process + asymmetric edge swaps → vertex-inhomogeneous graph

import random

def _max_IS(adj, N):
    """Branch-and-bound max independent set for small N."""
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands:
            if cur > best[0]: best[0] = cur
            return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur)
        bb(cands - {v} - adj[v], cur + 1)
    bb(set(range(N)), 0)
    return best[0]

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

    if N > 45:
        return [(u,v) for u in range(N) for v in adj[u] if v > u]

    max_iters = 2000 if N <= 38 else 500
    cur_alpha = _max_IS(adj, N)

    all_pairs = set((min(i,j), max(i,j)) for i in range(N) for j in range(i+1,N))
    edges = set((min(u,v), max(u,v)) for u in range(N) for v in adj[u] if v > u)

    for _ in range(max_iters):
        if cur_alpha <= 5: break
        e_list = list(edges)
        rng.shuffle(e_list)
        ne_list = list(all_pairs - edges)
        rng.shuffle(ne_list)
        improved = False
        for u, v in e_list[:30]:
            adj[u].discard(v); adj[v].discard(u)
            for a, b in ne_list[:50]:
                if b not in adj[a] and len(adj[a]) < cap and len(adj[b]) < cap and not has_k4(a, b):
                    adj[a].add(b); adj[b].add(a)
                    new_alpha = _max_IS(adj, N)
                    if new_alpha < cur_alpha:
                        edges.discard((min(u,v), max(u,v)))
                        edges.add((min(a,b), max(a,b)))
                        ne_list.remove((min(a,b), max(a,b)))
                        ne_list.append((min(u,v), max(u,v)))
                        cur_alpha = new_alpha; improved = True; break
                    adj[a].discard(b); adj[b].discard(a)
            if improved: break
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
