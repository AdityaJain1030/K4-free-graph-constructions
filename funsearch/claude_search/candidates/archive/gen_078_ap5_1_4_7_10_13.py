def construct(N):
    """10-regular circulant with AP offsets {1,4,7,10,13}: all ≡1 mod 3, diffs ≡0 mod 3 => K4-free."""
    S = [s for s in [1, 4, 7, 10, 13] if s < N // 2 + 1]
    seen = set()
    edges = []
    for i in range(N):
        for s in S:
            for j in [(i + s) % N, (i - s) % N]:
                key = (min(i, j), max(i, j))
                if key not in seen and key[0] != key[1]:
                    seen.add(key); edges.append(key)
    return edges
