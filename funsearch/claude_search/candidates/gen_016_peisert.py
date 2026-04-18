"""Peisert-like graph on F_q, q = p^2, p prime, p ≡ 3 mod 4.

Paley's cousin: connection set = {x^4 : x in F_q^*} ∪ {g·x^4} for a fixed
non-fourth-power g. Gives a self-complementary SRG different from Paley.
"""


def construct(N):
    p = 2
    for cand in range(3, 20):
        d = True
        for k in range(2, int(cand ** 0.5) + 1):
            if cand % k == 0:
                d = False
                break
        if d and cand % 4 == 3 and cand * cand <= N:
            p = cand
    q = p * p
    if q > N or q < 9:
        return []
    # Represent F_q as F_p[x] / (x^2 - ng), ng = non-square in F_p
    ng = next(k for k in range(1, p) if pow(k, (p - 1) // 2, p) == p - 1)
    def mul(a, b):
        return ((a[0]*b[0] + a[1]*b[1]*ng) % p, (a[0]*b[1] + a[1]*b[0]) % p)
    elts = [(a, b) for a in range(p) for b in range(p)]
    idx = {e: i for i, e in enumerate(elts)}
    fourth_powers = set()
    for e in elts:
        if e == (0, 0):
            continue
        e2 = mul(e, e)
        fourth_powers.add(mul(e2, e2))
    edges = []
    for i, a in enumerate(elts):
        for j in range(i + 1, len(elts)):
            diff = ((a[0] - elts[j][0]) % p, (a[1] - elts[j][1]) % p)
            if diff in fourth_powers:
                edges.append((i, j))
    return edges
