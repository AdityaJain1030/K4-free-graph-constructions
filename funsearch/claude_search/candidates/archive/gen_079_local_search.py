import random

def construct(N):
    """Start from {2,3,5} circulant, random edge swaps to reduce independence number."""
    random.seed(N * 17 + 3)

    # Build initial {2,3,5} circulant
    adj = [set() for _ in range(N)]
    def add_edge(u, v):
        adj[u].add(v); adj[v].add(u)
    def rem_edge(u, v):
        adj[u].discard(v); adj[v].discard(u)

    for i in range(N):
        for s in [2, 3, 5]:
            j = (i + s) % N
            add_edge(i, j)
            j = (i - s) % N
            add_edge(i, j)

    def is_k4_free_local(u, v):
        """Check if adding edge u-v creates K4."""
        common = adj[u] & adj[v]
        return not any(w in adj[x] for w in common for x in common if w < x)

    def greedy_alpha():
        best = 0
        for _ in range(30):
            order = list(range(N)); random.shuffle(order)
            indep, used = [], set()
            for v in order:
                if v not in used:
                    indep.append(v); used |= adj[v]
            best = max(best, len(indep))
        return best

    alpha = greedy_alpha()
    edges = [(u, v) for u in range(N) for v in adj[u] if u < v]
    import time; t0 = time.time()

    while time.time() - t0 < 3.5:
        # Random edge swap: pick (a,b),(c,d), try swap to (a,c),(b,d)
        (a, b) = random.choice(edges)
        (c, d) = random.choice(edges)
        if len({a, b, c, d}) < 4: continue
        if c in adj[a] or d in adj[b]: continue
        # Swap: remove ab,cd, add ac,bd
        rem_edge(a, b); rem_edge(c, d)
        if is_k4_free_local(a, c) and is_k4_free_local(b, d):
            add_edge(a, c); add_edge(b, d)
            new_alpha = greedy_alpha()
            if new_alpha <= alpha:
                alpha = new_alpha
                edges = [(u, v) for u in range(N) for v in adj[u] if u < v]
            else:
                rem_edge(a, c); rem_edge(b, d)
                add_edge(a, b); add_edge(c, d)
        else:
            add_edge(a, b); add_edge(c, d)

    return [(u, v) for u in range(N) for v in adj[u] if u < v]
