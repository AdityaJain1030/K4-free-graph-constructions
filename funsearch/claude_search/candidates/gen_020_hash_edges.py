"""Hash-defined edges with K4-rejection filter.

Deterministic hash h(i,j) = (i*a ^ j*b) mod m; accept edge iff below density
threshold AND doesn't close a K4. Like random greedy but with a structured,
reproducible edge order.
"""


def construct(N):
    a, b, m = 73856093, 19349663, 31
    edges = []
    adj = [set() for _ in range(N)]
    pairs = sorted(((((i * a) ^ (j * b)) % m, i, j)
                    for i in range(N) for j in range(i + 1, N)))
    for _, i, j in pairs:
        common = adj[i] & adj[j]
        k4 = False
        for u in common:
            if common & adj[u]:
                k4 = True
                break
        if k4:
            continue
        adj[i].add(j)
        adj[j].add(i)
        edges.append((i, j))
    return edges
