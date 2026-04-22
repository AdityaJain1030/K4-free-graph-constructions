import random

def construct(N):
    """Random-greedy K4-free graph: add edges in random order, skip any creating K4."""
    random.seed(N * 31 + 7)
    adj = [set() for _ in range(N)]
    pairs = [(i, j) for i in range(N) for j in range(i + 1, N)]
    random.shuffle(pairs)
    edges = []
    for u, v in pairs:
        # Check if adding (u,v) creates K4: need 2 common neighbors that are adjacent
        common = adj[u] & adj[v]
        if any(w in adj[x] for w in common for x in common if w < x):
            continue
        adj[u].add(v); adj[v].add(u)
        edges.append((u, v))
    return edges
