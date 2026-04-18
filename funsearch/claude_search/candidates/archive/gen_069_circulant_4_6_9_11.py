def construct(N):
    """Circulant C(N,{±4,±6,±9,±11}). Pairwise diffs {2,3,5,7} not in S => triangle-free nbhds => K4-free."""
    S = [4, 6, 9, 11]
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
