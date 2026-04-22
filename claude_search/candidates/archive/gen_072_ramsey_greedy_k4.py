# Family: random_process
# Catalog: ramsey_greedy_triangle_shadow
# Parent: gen_019_ramsey_structured_base (phase 1: K3-free; phase 2: K4-free; no RR base)
# Hypothesis: starting from K3-free dense random graph gives better α when K4-free edges added
# Why non-VT: random phase-1 ordering breaks symmetry; final graph is generically non-VT

import random
import math

def construct(N):
    rng = random.Random(N * 13 + 17)
    adj = [set() for _ in range(N)]

    # Phase 1: build K3-free graph (no triangles)
    def has_triangle(u, v):
        return bool(adj[u] & adj[v])

    pairs = [(i,j) for i in range(N) for j in range(i+1,N)]
    rng.shuffle(pairs)
    target_density = int(math.sqrt(N * math.log(N)))
    k3_edges = 0
    for u, v in pairs:
        if not has_triangle(u, v):
            adj[u].add(v); adj[v].add(u)
            k3_edges += 1
            if k3_edges >= target_density: break

    # Phase 2: add K4-free edges (triangles now allowed)
    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    cap = int(N**0.5) + 2
    more_pairs = [(i,j) for i,j in pairs if j not in adj[i]]
    rng.shuffle(more_pairs)
    for u, v in more_pairs:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
