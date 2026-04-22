# Family: polarity
# Catalog: er_polarity
# Parent: gen_008_er_polarity (hill-climb edge swaps to reduce α while keeping K4-free at valid N)
# Hypothesis: local search (edge-swap hill climbing) starting from ER(7) can reduce α to ~10 at N=57
# Why non-VT: ER base has two orbits; edge swaps with seeded order preserve non-VT structure

import random

def _er_adj(q, N):
    p = q
    seen = {}; pts = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z)==(0,0,0): continue
                if x!=0: iv=pow(x,p-2,p); rep=(1,(y*iv)%p,(z*iv)%p)
                elif y!=0: iv=pow(y,p-2,p); rep=(0,1,(z*iv)%p)
                else: rep=(0,0,1)
                if rep not in seen: seen[rep]=len(pts); pts.append(rep)
    adj=[set() for _ in range(N)]
    for i in range(N):
        for j in range(i+1,N):
            if sum(pts[i][k]*pts[j][k] for k in range(3))%p==0:
                adj[i].add(j); adj[j].add(i)
    return adj

def _alpha(adj, N):
    """Greedy independent set size (upper bound on α is hard; use greedy lower bound)."""
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    indep = set()
    blocked = set()
    for v in order:
        if v not in blocked:
            indep.add(v)
            blocked |= adj[v]
    return len(indep)

def construct(N):
    q = None
    for qq in range(2,20):
        if qq*qq+qq+1==N and all(qq%d!=0 for d in range(2,qq)): q=qq; break
    if not q: return []

    adj = _er_adj(q, N)

    def has_k4(u,v):
        common=list(adj[u]&adj[v])
        for a in range(len(common)):
            for b in range(a+1,len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    rng = random.Random(N * 53 + 7)
    alpha_cur = _alpha(adj, N)

    for _ in range(500):
        # Try: remove edge (u,v), add edge (a,b) not currently present
        edges = [(u,v) for u in range(N) for v in adj[u] if v>u]
        if not edges: break
        u, v = edges[rng.randint(0, len(edges)-1)]
        # Remove it
        adj[u].discard(v); adj[v].discard(u)
        # Try to add a new edge
        non_edges = [(a,b) for a in range(N) for b in adj[a] if b>a]
        # Instead, random non-edge
        a = rng.randint(0, N-1)
        b = rng.randint(0, N-1)
        if a!=b and b not in adj[a] and not has_k4(a,b):
            adj[a].add(b); adj[b].add(a)
            new_alpha = _alpha(adj, N)
            if new_alpha <= alpha_cur:
                alpha_cur = new_alpha
            else:
                adj[a].discard(b); adj[b].discard(a)
                adj[u].add(v); adj[v].add(u)
        else:
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v>u]
