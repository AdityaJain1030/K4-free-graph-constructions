def construct(N: int) -> list[tuple[int, int]]:
    """Random K4-free graph targeting ~d_max/2 regular degree."""
    import random
    random.seed(42)

    adj = [set() for _ in range(N)]
    target_deg = max(3, N // 4)

    # Shuffle and try to add edges
    all_edges = [(i, j) for i in range(N) for j in range(i + 1, N)]
    random.shuffle(all_edges)

    for i, j in all_edges:
        if len(adj[i]) >= target_deg or len(adj[j]) >= target_deg:
            continue

        neighbors_i = adj[i]
        neighbors_j = adj[j]
        common = neighbors_i & neighbors_j

        if len(common) < 2:
            adj[i].add(j)
            adj[j].add(i)

    edges = [(i, j) for i in range(N) for j in adj[i] if i < j]
    return edges
