def construct(N):
    """8-regular circulant C(N,{±2,±4,±5,±7}). Pairwise diffs {1,2,3,5} not in S => triangle-free nbhds."""
    S = [2, 4, 5, 7]
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
