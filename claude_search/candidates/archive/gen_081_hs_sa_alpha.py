# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: gen_069_hs_graph (SA on HS with exact IS objective; more targeted moves vs gen_069 random swaps)
# Hypothesis: exact-IS-guided SA on HS(N=50) can reach α=12 (c=12*7/(50*ln7)=0.863) vs current α=15
# Why non-VT: random edge swaps break HS automorphism group; swap sequence is seed-dependent

import random, math

def _exact_alpha(adj, N):
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands: best[0] = max(best[0], cur); return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur); bb(cands - {v} - adj[v], cur+1)
    bb(set(range(N)), 0)
    return best[0]

def _has_k4(adj, u, v):
    cm = list(adj[u] & adj[v])
    for a in range(len(cm)):
        for b in range(a+1, len(cm)):
            if cm[b] in adj[cm[a]]: return True
    return False

def construct(N):
    if N != 50: return []
    adj = [set() for _ in range(50)]
    for i in range(5):
        for j in range(5):
            adj[i*5+j].add(i*5+(j+1)%5); adj[i*5+(j+1)%5].add(i*5+j)
    inner = [5,7,9,6,8]
    for i in range(5): adj[inner[i]].add(inner[(i+2)%5]); adj[inner[(i+2)%5]].add(inner[i])
    for i in range(5): adj[i].add(i+5); adj[i+5].add(i)
    for i in range(5):
        for j in range(5):
            for k in range(5):
                u=i*5+k; v=25+j*5+(i*j+k)%5
                adj[u].add(v); adj[v].add(u)

    rng = random.Random(N * 12317 + 83)
    cur_a = _exact_alpha(adj, N)
    T = 1.5

    for step in range(80):
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
        if not edges or not non_edges: break
        u1,v1 = rng.choice(edges); u2,v2 = rng.choice(non_edges)
        adj[u1].discard(v1); adj[v1].discard(u1)
        if not _has_k4(adj, u2, v2):
            adj[u2].add(v2); adj[v2].add(u2)
            new_a = _exact_alpha(adj, N)
            delta = new_a - cur_a
            if delta < 0 or rng.random() < math.exp(-delta / max(T, 0.01)):
                cur_a = new_a
            else:
                adj[u2].discard(v2); adj[v2].discard(u2)
                adj[u1].add(v1); adj[v1].add(u1)
        else:
            adj[u1].add(v1); adj[v1].add(u1)
        T *= 0.96

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
