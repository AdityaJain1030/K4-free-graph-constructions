def construct(N: int) -> list[tuple[int, int]]:
    """Greedily add edges avoiding K4 formation."""
    from itertools import combinations

    adj = [set() for _ in range(N)]
    edges = []

    # Try to add edges in order of "distance" in ring
    candidates = []
    for i in range(N):
        for j in range(i + 1, N):
            dist = min(j - i, N - (j - i))
            candidates.append((dist, i, j))

    candidates.sort()

    for _, i, j in candidates:
        # Check if adding (i,j) creates a K4
        # K4 = 4 vertices all pairwise connected
        # Check all 4-subsets containing i, j
        neighbors_i = adj[i]
        neighbors_j = adj[j]
        common = neighbors_i & neighbors_j

        # If there are 2+ common neighbors, adding (i,j) creates K4
        if len(common) < 2:
            adj[i].add(j)
            adj[j].add(i)
            edges.append((i, j))

    return edges
