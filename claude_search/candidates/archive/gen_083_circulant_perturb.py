# Family: voltage_partial
# Catalog: asymmetric_lift_generic
# Parent: gen_070_petersen_lift (circulant on Z_N as base; perturb 3 edges to break VT; K4-free check)
# Hypothesis: best circulant C(N,S) has small α; 3-edge perturbation breaks VT without hurting α
# Why non-VT: 3 asymmetric edge swaps destroy the cyclic automorphism group

import random

def construct(N):
    rng = random.Random(N * 51817 + 97)

    def has_k4(adj, u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    def greedy_is(adj, N):
        deg = [len(adj[i]) for i in range(N)]
        order = sorted(range(N), key=lambda x: deg[x])
        IS = set(); blocked = set()
        for v in order:
            if v not in blocked: IS.add(v); blocked |= adj[v]
        return len(IS)

    best_a = N; best_adj = None

    # Try random symmetric connection sets of varying size
    for trial in range(30):
        k = rng.randint(3, min(9, N//4))
        # Build symmetric S: pairs {s, N-s}
        available = list(range(1, N//2 + 1))
        rng.shuffle(available)
        S = set()
        for s in available[:k]:
            S.add(s); S.add(N - s)

        adj = [set() for _ in range(N)]
        for v in range(N):
            for s in S:
                u = (v + s) % N
                if u != v: adj[v].add(u)
        # Check K4-free
        ok = True
        for u in range(N):
            for v in list(adj[u]):
                if v <= u: continue
                if has_k4(adj, u, v): ok = False; break
            if not ok: break
        if not ok:
            # Remove K4 edges
            changed = True
            while changed:
                changed = False
                for u in range(N):
                    for v in list(adj[u]):
                        if v <= u: continue
                        if has_k4(adj, u, v):
                            adj[u].discard(v); adj[v].discard(u); changed=True; break
                    if changed: break

        a = greedy_is(adj, N)
        if a < best_a:
            best_a = a; best_adj = [s.copy() for s in adj]

    if best_adj is None: return []
    adj = best_adj

    # Perturb: swap 3 edges to break VT (circulant aut group)
    for _ in range(3):
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
        if not edges or not non_edges: break
        u1,v1 = rng.choice(edges); u2,v2 = rng.choice(non_edges)
        adj[u1].discard(v1); adj[v1].discard(u1)
        if not has_k4(adj, u2, v2):
            adj[u2].add(v2); adj[v2].add(u2)
        else:
            adj[u1].add(v1); adj[v1].add(u1)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
