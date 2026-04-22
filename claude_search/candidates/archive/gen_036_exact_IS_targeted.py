# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_030_exact_alpha_hillclimb (target exact IS members for edge insertion, not random non-edges)
# Hypothesis: inserting edges within exact IS (not random) reaches α≤6 at N=33 within 5s budget
# Why non-VT: IS-targeted edge pattern creates structurally inhomogeneous vertex neighborhoods

import random

def _exact_IS(adj, N):
    """Find exact max independent set via branch-and-bound, return the IS."""
    best_IS = [[]]
    def bb(cands, cur_IS):
        if len(cur_IS) + len(cands) <= len(best_IS[0]): return
        if not cands:
            if len(cur_IS) > len(best_IS[0]): best_IS[0] = list(cur_IS)
            return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur_IS)
        bb(cands - {v} - adj[v], cur_IS + [v])
    bb(set(range(N)), [])
    return set(best_IS[0])

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

    # Hill climbing: find exact IS, try to connect IS pairs via edge swaps
    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
    cur_IS = _exact_IS(adj, N)

    for _ in range(150):
        if len(cur_IS) <= 5: break
        IS_list = list(cur_IS)
        rng.shuffle(IS_list)
        improved = False

        # Try to add edge between two IS members directly
        for i in range(len(IS_list)):
            for j in range(i+1, len(IS_list)):
                u, v = IS_list[i], IS_list[j]
                if v in adj[u]: continue
                if len(adj[u]) >= cap or len(adj[v]) >= cap: continue
                if not has_k4(u, v):
                    adj[u].add(v); adj[v].add(u)
                    new_IS = _exact_IS(adj, N)
                    if len(new_IS) < len(cur_IS):
                        edges.append((min(u,v), max(u,v)))
                        cur_IS = new_IS; improved = True; break
                    adj[u].discard(v); adj[v].discard(u)
            if improved: break

        if not improved:
            # Try edge swap: remove one edge, add IS-connecting edge
            rng.shuffle(edges)
            for eu, ev in edges[:15]:
                adj[eu].discard(ev); adj[ev].discard(eu)
                for i in range(len(IS_list)):
                    for j in range(i+1, min(i+5, len(IS_list))):
                        u, v = IS_list[i], IS_list[j]
                        if v in adj[u] or len(adj[u])>=cap or len(adj[v])>=cap: continue
                        if not has_k4(u, v):
                            adj[u].add(v); adj[v].add(u)
                            new_IS = _exact_IS(adj, N)
                            if len(new_IS) < len(cur_IS):
                                edges.remove((min(eu,ev),max(eu,ev)))
                                edges.append((min(u,v),max(u,v)))
                                cur_IS = new_IS; improved = True; break
                            adj[u].discard(v); adj[v].discard(u)
                    if improved: break
                if improved: break
                adj[eu].add(ev); adj[ev].add(eu)
            if not improved: break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
