# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (MCMC edge-swaps to randomize the regular graph differently)
# Hypothesis: MCMC-uniformized regular graph before K4 removal has better expansion → smaller α
# Why non-VT: MCMC swaps create non-isomorphic graph from configuration model; different Aut structure

import random

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 101 + 61)

    # Build initial regular graph: vertex v connected to v±1, v±2, ... (circulant start)
    adj = [set() for _ in range(N)]
    for v in range(N):
        for k in range(1, target_d // 2 + 1):
            u = (v + k) % N
            adj[v].add(u); adj[u].add(v)
        if target_d % 2 == 1:
            u = (v + N // 2) % N
            adj[v].add(u); adj[u].add(v)

    # MCMC: random edge swaps to mix
    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
    for _ in range(N * target_d * 3):
        i, j = rng.randint(0, len(edges)-1), rng.randint(0, len(edges)-1)
        if i == j: continue
        a, b = edges[i]; c, d = edges[j]
        if len({a,b,c,d}) < 4: continue
        # Swap: (a,b),(c,d) → (a,c),(b,d) or (a,d),(b,c)
        if rng.random() < 0.5:
            new_e1, new_e2 = (min(a,c),max(a,c)), (min(b,d),max(b,d))
        else:
            new_e1, new_e2 = (min(a,d),max(a,d)), (min(b,c),max(b,c))
        nu1, nv1 = new_e1; nu2, nv2 = new_e2
        if nv1 in adj[nu1] or nv2 in adj[nu2]: continue
        adj[a].discard(b); adj[b].discard(a)
        adj[c].discard(d); adj[d].discard(c)
        adj[nu1].add(nv1); adj[nv1].add(nu1)
        adj[nu2].add(nv2); adj[nv2].add(nu2)
        edges[i] = new_e1; edges[j] = new_e2

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
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
