# Family: core_periphery
# Catalog: asymmetric_lift_generic
# Parent: gen_024_full_crossedge_lift (Hoffman-Singleton graph N=50, girth 5, K4-free, then perturb)
# Hypothesis: HS graph has girth 5 (K4-free), α=15; random edge swaps may reduce α toward target
# Why non-VT: random edge swaps break the transitive HS automorphism group

import random

def construct(N):
    if N != 50:
        # Fallback: RR K4-free at other N
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
        changed = True
        while changed:
            changed = False
            for u in range(N):
                for v in list(adj[u]):
                    if v <= u: continue
                    cm = list(adj[u] & adj[v])
                    for a in range(len(cm)):
                        for b in range(a+1, len(cm)):
                            if cm[b] in adj[cm[a]]:
                                adj[u].discard(v); adj[v].discard(u); changed=True; break
                        if changed: break
                    if changed: break
                if changed: break
        return [(u,v) for u in range(N) for v in adj[u] if v > u]

    # Hoffman-Singleton graph: 5 pentagons + 5 pentagrams
    adj = [set() for _ in range(50)]
    # Pentagon P_i: vertices i*5+j, edges j~j+1 mod 5
    # Pentagram Q_j: vertices 25+j*5+k, edges k~k+2 mod 5
    for i in range(5):
        for j in range(5):
            adj[i*5+j].add(i*5+(j+1)%5); adj[i*5+(j+1)%5].add(i*5+j)
    for j in range(5):
        for k in range(5):
            adj[25+j*5+k].add(25+j*5+(k+2)%5); adj[25+j*5+(k+2)%5].add(25+j*5+k)
    # Between P_i and Q_j: vertex (i,k) in P_i connects to (j, (i*j+k) mod 5) in Q_j
    for i in range(5):
        for j in range(5):
            for k in range(5):
                u = i*5+k
                v = 25+j*5+(i*j+k)%5
                adj[u].add(v); adj[v].add(u)

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    # Random edge swaps to break symmetry
    rng = random.Random(N * 113 + 37)
    for _ in range(100):
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        if not edges: break
        u1, v1 = rng.choice(edges)
        non_edges = [(a,b) for a in range(N) for b in range(a+1,N) if b not in adj[a]]
        if not non_edges: break
        u2, v2 = rng.choice(non_edges)
        adj[u1].discard(v1); adj[v1].discard(u1)
        if not has_k4(u2, v2):
            adj[u2].add(v2); adj[v2].add(u2)
        else:
            adj[u1].add(v1); adj[v1].add(u1)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
