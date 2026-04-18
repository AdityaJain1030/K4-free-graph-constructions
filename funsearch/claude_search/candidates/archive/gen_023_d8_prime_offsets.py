def construct(N: int) -> list[tuple[int, int]]:
    offsets = [1, 2, 5, 11]
    edges = set()
    for i in range(N):
        for d in offsets:
            j = (i + d) % N
            if i != j:
                edges.add((min(i,j), max(i,j)))
            j = (i - d) % N
            if i != j:
                edges.add((min(i,j), max(i,j)))
    return list(edges)
