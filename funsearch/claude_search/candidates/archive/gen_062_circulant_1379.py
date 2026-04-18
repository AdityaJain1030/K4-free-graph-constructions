def construct(N):
    """8-regular circulant C(N, {1,3,7,9}). Pairwise diffs {2,4,6,8} not in S => K4-free."""
    S = [1, 3, 7, 9]
    edges = []
    for i in range(N):
        for s in S:
            j = (i + s) % N
            if i < j:
                edges.append((i, j))
    return edges
