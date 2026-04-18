"""Cayley graph of dihedral group D_n with connection set {r, r^-1, s}.

Elements: (type, i) with type ∈ {0, 1}, i ∈ Z/n. 3-regular.
A 3-regular graph contains K4 only if the graph is K4 itself (|V|=4), so for
n >= 3 this is K4-free.
"""


def construct(N):
    n = N // 2
    if n < 3:
        return []
    enc = lambda t, i: t * n + (i % n)
    edges = set()
    for t in range(2):
        for i in range(n):
            v = enc(t, i)
            if t == 0:
                r_plus = enc(0, i + 1)
                r_minus = enc(0, i - 1)
                s_neighbor = enc(1, i)
            else:
                r_plus = enc(1, i - 1)
                r_minus = enc(1, i + 1)
                s_neighbor = enc(0, i)
            for w in (r_plus, r_minus, s_neighbor):
                if v != w:
                    edges.add((min(v, w), max(v, w)))
    return list(edges)
