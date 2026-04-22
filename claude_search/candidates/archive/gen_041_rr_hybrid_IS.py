# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (exact IS climb at N≤32, greedy at N>32; target α≤5 at N=30)
# Hypothesis: random regular base at N=30 has favorable IS structure; exact climb can reach α≤5
# Why non-VT: RR construction + non-uniform edge modifications → asymmetric vertex neighborhoods

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

def _greedy_alpha(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    cap = target_d + 1
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
                            adj[u].discard(v); adj[v].discard(u); changed = True; break
                    if changed: break
                if changed: break
            if changed: break

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    use_exact = N <= 32
    alpha_fn = _exact_alpha if use_exact else _greedy_alpha
    max_iters = 100 if use_exact else 200
    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
    ne = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    cur = alpha_fn(adj, N)

    for _ in range(max_iters):
        if cur <= 5: break
        rng.shuffle(edges); rng.shuffle(ne)
        improved = False
        for eu, ev in edges[:20]:
            adj[eu].discard(ev); adj[ev].discard(eu)
            for a, b in ne[:30]:
                if b not in adj[a] and len(adj[a])<=cap and len(adj[b])<=cap and not has_k4(a,b):
                    adj[a].add(b); adj[b].add(a)
                    new = alpha_fn(adj, N)
                    if new < cur:
                        edges.remove((min(eu,ev),max(eu,ev))); edges.append((min(a,b),max(a,b)))
                        ne.remove((min(a,b),max(a,b))); ne.append((min(eu,ev),max(eu,ev)))
                        cur = new; improved = True; break
                    adj[a].discard(b); adj[b].discard(a)
            if improved: break
            adj[eu].add(ev); adj[ev].add(eu)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
