# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_026_bohman_degree_cap (exact-α guided edge-swap hill climbing on degree-capped graph)
# Hypothesis: edge swaps guided by exact IS shrinking can reduce α from 9 to ≤6 at N=32-35
# Why non-VT: seeded process + asymmetric edge swaps → vertex-inhomogeneous graph

import random

def _exact_alpha(adj, N, limit=8):
    """Branch-and-bound max independent set, capped at limit (returns limit if IS size > limit found)."""
    best = [0]
    def bb(cands, cur_IS):
        if len(cur_IS) + len(cands) <= best[0]:
            return
        if not cands:
            if len(cur_IS) > best[0]:
                best[0] = len(cur_IS)
            return
        v = max(cands, key=lambda x: len(adj[x] & cands))  # branch on max-degree
        # Branch: exclude v
        bb(cands - {v}, cur_IS)
        # Branch: include v
        bb(cands - {v} - adj[v], cur_IS | {v})

    bb(set(range(N)), set())
    return best[0]

def construct(N):
    if N > 50:
        # Too slow for large N, fall back to capped process
        cap = int(N**0.5) + 2
    else:
        cap = int(N**0.5) + 2

    rng = random.Random(N * 43 + 11)
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Phase 1: degree-capped K4-free process
    pairs = [(i,j) for i in range(N) for j in range(i+1,N)]
    rng.shuffle(pairs)
    for u, v in pairs:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    if N > 40:
        return [(u,v) for u in range(N) for v in adj[u] if v > u]

    # Phase 2: edge-swap hill climbing guided by IS size
    all_pairs = set((min(i,j), max(i,j)) for i in range(N) for j in range(i+1,N))
    edges = set((min(u,v), max(u,v)) for u in range(N) for v in adj[u] if v > u)
    non_edges = all_pairs - edges

    cur_alpha = _exact_alpha(adj, N)

    for _ in range(200):
        if cur_alpha <= 5: break
        # Try: remove a random edge, add a non-edge between IS members
        e_list = list(edges)
        rng.shuffle(e_list)
        improved = False
        for u, v in e_list[:20]:
            adj[u].discard(v); adj[v].discard(u)
            # Find two non-adjacent IS vertices
            ne_list = list(non_edges - {(u,v) if u<v else (v,u)})
            rng.shuffle(ne_list)
            for a, b in ne_list[:30]:
                if b not in adj[a] and len(adj[a]) < cap and len(adj[b]) < cap and not has_k4(a, b):
                    adj[a].add(b); adj[b].add(a)
                    new_alpha = _exact_alpha(adj, N)
                    if new_alpha < cur_alpha:
                        edges.discard((min(u,v), max(u,v)))
                        edges.add((min(a,b), max(a,b)))
                        non_edges.add((min(u,v), max(u,v)))
                        non_edges.discard((min(a,b), max(a,b)))
                        cur_alpha = new_alpha
                        improved = True
                        break
                    adj[a].discard(b); adj[b].discard(a)
            if improved: break
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
