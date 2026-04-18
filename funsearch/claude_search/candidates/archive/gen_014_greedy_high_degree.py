def construct(N: int) -> list[tuple[int, int]]:
    """Greedy K4-free with higher degree target (N/3)."""
    adj = [set() for _ in range(N)]
    edges = []

    # Try to add edges in order of "distance" in ring
    candidates = []
    for i in range(N):
        for j in range(i + 1, N):
            dist = min(j - i, N - (j - i))
            candidates.append((dist, i, j))

    candidates.sort()

    target_deg = max(3, N // 3)

    for _, i, j in candidates:
        if len(adj[i]) >= target_deg or len(adj[j]) >= target_deg:
            continue

        neighbors_i = adj[i]
        neighbors_j = adj[j]
        common = neighbors_i & neighbors_j

        if len(common) < 2:
            adj[i].add(j)
            adj[j].add(i)
            edges.append((i, j))

    return edges
