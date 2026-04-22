# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: gen_037_random_regular_k4free (use circulant base + non-VT edge swaps instead of RR)
# Hypothesis: circulant C(N, S) base with small α + 5 random non-VT edge swaps may give c < 0.9
# Why non-VT: 5 asymmetric edge swaps break the cyclic symmetry group of the circulant

import random

def _is_k4_free(adj, N):
    for u in range(N):
        for v in adj[u]:
            for w in adj[u] & adj[v]:
                for x in adj[u] & adj[v] & adj[w]:
                    return False
    return True

def construct(N):
    rng = random.Random(N * 113 + 73)

    def build_circ(N, gens):
        adj = [set() for _ in range(N)]
        for v in range(N):
            for g in gens:
                u = (v + g) % N
                if u != v: adj[v].add(u); adj[u].add(v)
        return adj

    def has_k4(adj, u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    def greedy_alpha(adj, N):
        deg = [len(adj[i]) for i in range(N)]
        order = sorted(range(N), key=lambda x: deg[x])
        IS = set(); blocked = set()
        for v in order:
            if v not in blocked: IS.add(v); blocked |= adj[v]
        return len(IS)

    # Try several generator sets
    best_adj = None; best_alpha = N
    d_target = int(N**0.5) + 1

    for trial in range(10):
        # Random generator set
        gens = set()
        attempts = list(range(1, N//2 + 1))
        rng.shuffle(attempts)
        for g in attempts:
            if len(gens) >= d_target // 2: break
            gens.add(g)
        gens = sorted(gens)

        adj = build_circ(N, gens)
        # Check K4-free by checking local structure
        ok = True
        for u in range(N):
            for v in adj[u]:
                if v > u:
                    for w in adj[u] & adj[v]:
                        for x in adj[u] & adj[v] & adj[w]:
                            ok = False; break
                        if not ok: break
                    if not ok: break
            if not ok: break

        if ok:
            a = greedy_alpha(adj, N)
            if a < best_alpha:
                best_alpha = a; best_adj = [s.copy() for s in adj]

    if best_adj is None:
        return []

    adj = best_adj

    # Non-VT perturbation: swap 5 edges asymmetrically
    def swap_edge(adj, u, v, a, b):
        adj[u].discard(v); adj[v].discard(u)
        adj[a].add(b); adj[b].add(a)

    edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
    ne = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(ne)

    swaps_done = 0
    for a, b in ne[:20]:
        if not has_k4(adj, a, b):
            # Remove a random edge incident to a or b
            incident = [(min(a,x),max(a,x)) for x in adj[a] if x != b] + \
                       [(min(b,x),max(b,x)) for x in adj[b] if x != a]
            if incident:
                eu, ev = rng.choice(incident)
                adj[eu].discard(ev); adj[ev].discard(eu)
                adj[a].add(b); adj[b].add(a)
                swaps_done += 1
                if swaps_done >= 5: break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
