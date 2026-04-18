# Family: cayley_product
"""Cayley graph on Z/p × Z/q using QR connection sets."""

def construct(N):
    # Smaller prime powers to get higher density
    candidates = {
        9: (3, 3),    # 3×3, connect via all mod 3
        25: (5, 5),
        49: (7, 7),
    }
    if N not in candidates:
        return []

    p, q = candidates[N]

    # For small primes, use all nonzero residues as connection set
    conns_p = set(range(1, p))
    conns_q = set(range(1, q))

    edges = []
    for i in range(p):
        for j in range(q):
            u = i * q + j
            for a in conns_p:
                v_i = (i + a) % p
                v = v_i * q + j
                if u < v:
                    edges.append((u, v))
            for b in conns_q:
                v_j = (j + b) % q
                v = i * q + v_j
                if u < v:
                    edges.append((u, v))

    return list(set(edges))
