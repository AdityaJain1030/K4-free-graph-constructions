# Family: random_lift
"""Random lift of C_5 cycle with deterministic offsets."""

def construct(N):
    if N % 5 != 0:
        return []
    k = N // 5
    edges = []
    for i in range(5):
        i_next = (i + 1) % 5
        for j in range(k):
            u = i * k + j
            a = ((i * 23 + j * 17) % (k - 1) + 1) if k > 1 else 0
            v = i_next * k + ((j + a) % k)
            if u < v:
                edges.append((u, v))
    return edges
