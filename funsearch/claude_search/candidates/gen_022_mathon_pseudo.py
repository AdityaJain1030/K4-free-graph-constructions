"""Mathon-style pseudo-random SRG: Cayley on (Z/n)^2 with connection set built from
a union of cosets of a small subgroup. Mathon's construction produces non-isomorphic
SRGs with the same parameters as Paley; this is a simplified sketch.

For q = p^2, vertices = F_p × F_p, connection set = {(x, y) : y = x^2 mod p}
and its negatives. Not guaranteed K4-free; eval will filter.
"""


def construct(N):
    def is_prime(n):
        if n < 2: return False
        for k in range(2, int(n**0.5) + 1):
            if n % k == 0: return False
        return True

    p = 2
    for cand in range(3, 20):
        if is_prime(cand) and cand * cand <= N:
            p = cand
    q = p * p
    if q > N or p < 3:
        return []
    elts = [(a, b) for a in range(p) for b in range(p)]
    idx = {e: i for i, e in enumerate(elts)}
    # Connection set: (x, y) with y = x^2 or y = -x^2 (mod p), x != 0
    conn = set()
    for x in range(1, p):
        for s in (1, -1):
            y = (s * x * x) % p
            conn.add((x, y))
            conn.add(((-x) % p, y))
    edges = []
    for i, a in enumerate(elts):
        for j in range(i + 1, len(elts)):
            b = elts[j]
            diff = ((a[0] - b[0]) % p, (a[1] - b[1]) % p)
            if diff in conn:
                edges.append((i, j))
    return edges
