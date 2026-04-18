def construct(N: int) -> list[tuple[int, int]]:
    edges = set()
    for i in range(N):
        for f in [2, 11, 13]:
            edges.add((min(i, (i+f)%N), max(i, (i+f)%N)))
            edges.add((min(i, (i-f)%N), max(i, (i-f)%N)))
    return list(edges)
