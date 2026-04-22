# Family: voltage_partial
# Catalog: asymmetric_lift_generic
# Parent: gen_083_circulant_perturb (systematic search over circulant C(N,S); pick best greedy IS)
# Hypothesis: right connection set S in C(N,S) gives K4-free with much smaller α than random RR
# Why non-VT: 5 random asymmetric edge swaps after best circulant found break all Aut

import random

def _greedy_is(adj, N):
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = set(); blocked = set()
    for v in order:
        if v not in blocked: IS.add(v); blocked |= adj[v]
    return len(IS)

def _has_k4(adj, u, v):
    cm = list(adj[u] & adj[v])
    for a in range(len(cm)):
        for b in range(a+1, len(cm)):
            if cm[b] in adj[cm[a]]: return True
    return False

def construct(N):
    rng = random.Random(N * 777013 + 53)
    best_a = N; best_adj = None

    for trial in range(200):
        # Random symmetric connection set
        k = rng.randint(2, min(8, N//5))
        avail = list(range(1, N//2 + 1))
        rng.shuffle(avail)
        S = set()
        for s in avail[:k]: S.add(s); S.add(N - s)

        adj = [set() for _ in range(N)]
        for v in range(N):
            for s in S:
                u = (v + s) % N
                if u != v: adj[v].add(u)

        # K4 removal
        changed = True
        while changed:
            changed = False
            for u in range(N):
                for v in list(adj[u]):
                    if v <= u: continue
                    if _has_k4(adj, u, v):
                        adj[u].discard(v); adj[v].discard(u); changed=True; break
                if changed: break

        dm = max(len(adj[v]) for v in range(N))
        if dm < 2: continue
        a = _greedy_is(adj, N)
        if a < best_a: best_a = a; best_adj = [s.copy() for s in adj]

    if best_adj is None: return []
    adj = best_adj

    # Break VT: 5 asymmetric swaps
    for _ in range(5):
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
        if not edges or not non_edges: break
        u1,v1 = rng.choice(edges); u2,v2 = rng.choice(non_edges)
        adj[u1].discard(v1); adj[v1].discard(u1)
        if not _has_k4(adj, u2, v2):
            adj[u2].add(v2); adj[v2].add(u2)
        else:
            adj[u1].add(v1); adj[v1].add(u1)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
