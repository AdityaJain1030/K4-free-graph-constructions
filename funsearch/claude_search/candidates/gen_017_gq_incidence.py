"""Incidence graph of PG(2, q): bipartite with points + lines; point ~ line iff incident.

Bipartite → trivially K4-free. N = 2(q^2 + q + 1). Low c because bipartite means α ≥ N/2.
Included as a generalized-quadrangle / incidence-structure family exemplar.
"""


def construct(N):
    def is_prime(n):
        if n < 2: return False
        for k in range(2, int(n ** 0.5) + 1):
            if n % k == 0: return False
        return True
    q = 2
    for cand in range(3, 30):
        if is_prime(cand) and 2 * (cand * cand + cand + 1) <= N:
            q = cand
    npts = q * q + q + 1
    if 2 * npts > N:
        return []
    points = []
    seen = set()
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x, y, z) == (0, 0, 0): continue
                v = (x, y, z)
                piv = next(c for c in v if c)
                inv = pow(piv, q - 2, q) if q > 2 else 1
                key = tuple((a * inv) % q for a in v)
                if key not in seen:
                    seen.add(key)
                    points.append(key)
    lines = points[:]  # same coordinates, different role
    edges = []
    for i, p in enumerate(points):
        for j, L in enumerate(lines):
            if (p[0] * L[0] + p[1] * L[1] + p[2] * L[2]) % q == 0:
                edges.append((i, npts + j))
    return edges
