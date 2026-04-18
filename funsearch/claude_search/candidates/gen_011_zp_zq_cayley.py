def construct(N):
    """Per-N: use Z_p x Z_q Cayley for N=pq, else circulant {2,3,5}."""
    factorizations = {20: (4, 5), 40: (8, 5), 50: (10, 5), 60: (12, 5), 30: (6, 5), 25: (5, 5)}
    if N not in factorizations:
        seen = set()
        edges = []
        for i in range(N):
            for s in [2, 3, 5]:
                for j in [(i+s)%N, (i-s)%N]:
                    key = (min(i,j), max(i,j))
                    if key not in seen and key[0] != key[1]:
                        seen.add(key); edges.append(key)
        return edges

    p, q = factorizations[N]
    # Connection set: (±1,0),(0,±1),(1,1),(-1,-1)
    gens = [(1,0),(p-1,0),(0,1),(0,q-1),(1,1),(p-1,q-1)]
    seen = set()
    edges = []
    for a in range(p):
        for b in range(q):
            u = a*q + b
            for da, db in gens:
                a2, b2 = (a+da)%p, (b+db)%q
                v = a2*q + b2
                key = (min(u,v), max(u,v))
                if key not in seen and key[0] != key[1]:
                    seen.add(key); edges.append(key)
    return edges
