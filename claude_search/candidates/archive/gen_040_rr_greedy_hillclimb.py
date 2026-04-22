# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free + gen_030_exact_alpha_hillclimb (RR + fast greedy IS swaps)
# Hypothesis: random regular start + repeated greedy IS hill climb reduces α to ≤5 at N=30
# Why non-VT: random regular base + IS-targeted swaps → vertex-inhomogeneous graph

import random

def _greedy_alpha_k(adj, N, k=5):
    """Run k greedy IS trials with different orderings, return minimum."""
    rng2 = random.Random(sum(len(adj[i]) for i in range(N)) * 7)
    best = N
    order = list(range(N))
    for _ in range(k):
        rng2.shuffle(order)
        IS = set(); blocked = set()
        for v in order:
            if v not in blocked: IS.add(v); blocked |= adj[v]
        best = min(best, len(IS))
    return best

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 101 + 61)

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
    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    # Greedy IS hill climbing
    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
    ne = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    cur = _greedy_alpha_k(adj, N)

    for _ in range(300):
        if cur <= 5: break
        rng.shuffle(edges); rng.shuffle(ne)
        improved = False
        for eu, ev in edges[:15]:
            adj[eu].discard(ev); adj[ev].discard(eu)
            for a, b in ne[:30]:
                if b not in adj[a] and len(adj[a])<=cap and len(adj[b])<=cap and not has_k4(a,b):
                    adj[a].add(b); adj[b].add(a)
                    new = _greedy_alpha_k(adj, N)
                    if new < cur:
                        edges.remove((min(eu,ev),max(eu,ev))); edges.append((min(a,b),max(a,b)))
                        ne.remove((min(a,b),max(a,b))); ne.append((min(eu,ev),max(eu,ev)))
                        cur = new; improved = True; break
                    adj[a].discard(b); adj[b].discard(a)
            if improved: break
            adj[eu].add(ev); adj[ev].add(eu)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
