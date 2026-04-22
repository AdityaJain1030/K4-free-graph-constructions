# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free + gen_030_exact_alpha_hillclimb (RR start + exact IS hill climb)
# Hypothesis: random regular start (α=8) + exact IS swaps can reach α≤5 at N=30, giving c=0.60
# Why non-VT: random regular base + asymmetric IS-targeted swaps → vertex-inhomogeneous structure

import random

def _exact_alpha(adj, N):
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
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 101 + 61)

    # Random regular graph via configuration model
    stubs = []
    for v in range(N): stubs.extend([v] * target_d)
    rng.shuffle(stubs)
    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs)-1, 2):
        u, v = stubs[i], stubs[i+1]
        if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Remove K4 edges
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

    # Re-saturate
    candidates = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(candidates)
    for u, v in candidates:
        if len(adj[u]) <= target_d and len(adj[v]) <= target_d and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    if N > 45:
        return [(u,v) for u in range(N) for v in adj[u] if v > u]

    # Exact IS hill climbing
    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
    non_edges = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    cur_alpha = _exact_alpha(adj, N)
    cap = target_d + 1

    for _ in range(200):
        if cur_alpha <= 5: break
        rng.shuffle(edges); rng.shuffle(non_edges)
        improved = False
        for eu, ev in edges[:20]:
            adj[eu].discard(ev); adj[ev].discard(eu)
            for a, b in non_edges[:40]:
                if b not in adj[a] and len(adj[a])<=cap and len(adj[b])<=cap and not has_k4(a,b):
                    adj[a].add(b); adj[b].add(a)
                    new_alpha = _exact_alpha(adj, N)
                    if new_alpha < cur_alpha:
                        edges.remove((min(eu,ev),max(eu,ev))); edges.append((min(a,b),max(a,b)))
                        non_edges.remove((min(a,b),max(a,b))); non_edges.append((min(eu,ev),max(eu,ev)))
                        cur_alpha = new_alpha; improved = True; break
                    adj[a].discard(b); adj[b].discard(a)
            if improved: break
            adj[eu].add(ev); adj[ev].add(eu)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
