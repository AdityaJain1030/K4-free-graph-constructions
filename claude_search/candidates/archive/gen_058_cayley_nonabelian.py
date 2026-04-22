# Family: core_periphery
# Catalog: asymmetric_lift_generic
# Parent: gen_024_full_crossedge_lift (Cayley graph on non-abelian group S_n; then K4-free filter)
# Hypothesis: non-abelian Cayley has better expansion than circulant; smaller α
# Why non-VT: non-abelian group has non-transitive Cayley graph when generators not closed under Aut

import random
from itertools import permutations

def construct(N):
    # Use symmetric group S_k as vertex set where k! ≈ N
    import math
    k = 2
    while math.factorial(k+1) <= N: k += 1
    # Use S_k acting on [k]: vertices are permutations, N' = k!
    # Generators: all transpositions (i,j) and a random 3-cycle
    perm_list = list(permutations(range(k)))
    N2 = len(perm_list)
    if N2 < 34 or N2 > 200: return []

    def perm_mul(p, q):
        return tuple(p[q[i]] for i in range(k))
    def perm_inv(p):
        inv = [0]*k
        for i,x in enumerate(p): inv[x] = i
        return tuple(inv)

    idx = {p: i for i, p in enumerate(perm_list)}
    identity = tuple(range(k))

    # Generators: all transpositions
    gens = []
    for i in range(k):
        for j in range(i+1, k):
            t = list(range(k)); t[i], t[j] = t[j], t[i]
            gens.append(tuple(t))

    # Build Cayley graph
    adj = [set() for _ in range(N2)]
    for u, p in enumerate(perm_list):
        for g in gens:
            pg = perm_mul(p, g)
            v = idx.get(pg)
            if v is not None and v != u:
                adj[u].add(v); adj[v].add(u)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Remove K4 edges greedily
    changed = True
    while changed:
        changed = False
        for u in range(N2):
            for v in list(adj[u]):
                if v <= u: continue
                if has_k4(u, v):
                    adj[u].discard(v); adj[v].discard(u)
                    changed = True; break
            if changed: break

    return [(u,v) for u in range(N2) for v in adj[u] if v > u]
