def construct(N: int) -> list[tuple[int, int]]:
    import math
    # Pick 3 symmetric offsets coprime to N, spread across [1, N//2]
    candidates = [k for k in range(1, N//2) if math.gcd(k, N) == 1]
    step = max(1, len(candidates) // 4)
    offsets = [candidates[step], candidates[2*step], candidates[3*step]]
    edges = set()
    for i in range(N):
        for f in offsets:
            edges.add((min(i, (i+f)%N), max(i, (i+f)%N)))
            edges.add((min(i, (i-f)%N), max(i, (i-f)%N)))
    return list(edges)
