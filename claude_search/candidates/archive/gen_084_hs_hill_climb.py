# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: gen_081_hs_sa_alpha (hill-climbing only; no SA temperature; pure greedy IS descent)
# Hypothesis: greedy IS descent from HS base can reduce α from 15 to 12 via 300 edge-swap trials
# Why non-VT: edge swaps destroy HS automorphism; final graph has trivial Aut

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

    rng = random.Random(N * 33391 + 7)
    cur_a = _greedy_is(adj, N)

    # Pure hill-climb: only accept moves that reduce greedy IS
    no_improve = 0
    for step in range(500):
        edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
        non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
        if not edges or not non_edges: break
        u1,v1 = rng.choice(edges); u2,v2 = rng.choice(non_edges)
        adj[u1].discard(v1); adj[v1].discard(u1)
        if not _has_k4(adj, u2, v2):
            adj[u2].add(v2); adj[v2].add(u2)
            new_a = _greedy_is(adj, N)
            if new_a < cur_a:
                cur_a = new_a; no_improve = 0
            else:
                adj[u2].discard(v2); adj[v2].discard(u2)
                adj[u1].add(v1); adj[v1].add(u1)
                no_improve += 1
        else:
            adj[u1].add(v1); adj[v1].add(u1)
            no_improve += 1
        if no_improve > 100: break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
