def construct(N):
    """8-regular circulant C(N,{±2,±3,±7,±12}). Pairwise diffs outside S."""
    S = [2, 3, 7, 12]
    seen = set()
    edges = []
    for i in range(N):
        for s in S:
            for j in [(i + s) % N, (i - s) % N]:
                key = (min(i, j), max(i, j))
                if key not in seen and key[0] != key[1]:
                    seen.add(key)
                    edges.append(key)
    return edges
