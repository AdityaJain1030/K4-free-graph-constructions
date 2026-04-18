# Family: blowup
"""Blowup of C_5: replace each vertex with independent set, blow up edges."""

def construct(N):
    if N % 5 != 0:
        return []

    k = N // 5
    edges = []

    # C_5 edges: 0-1, 1-2, 2-3, 3-4, 4-0
    for u_base, v_base in [(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)]:
        for i in range(k):
            for j in range(k):
                u = u_base * k + i
                v = v_base * k + j
                if u < v:
                    edges.append((u, v))

    return edges
