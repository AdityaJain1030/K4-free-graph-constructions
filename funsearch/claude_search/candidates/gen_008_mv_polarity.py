# Mattheus-Verstraete inspired seed.
# Their 2024 Annals paper ("Asymptotics of r(4,t)") built K4-free pseudorandom
# graphs from unitary polarities of generalized quadrangles, achieving the
# long-conjectured t^3/log^4 t lower bound for R(4,t).
# This simplified version uses the orthogonal polarity graph of PG(2, p):
# vertices are projective points; two points adjacent iff their dot product
# vanishes mod p. Then a greedy pass removes any edge that closes a K4.

def construct(N):
    def is_prime(n):
        if n < 2: return False
        for k in range(2, int(n**0.5) + 1):
            if n % k == 0: return False
        return True

    p = 2
    for q in range(3, 200):
        if is_prime(q) and q * q + q + 1 <= N:
            p = q

    pts = []
    seen = set()
    for x in range(p):
        for y in range(p):
            for z in range(p):
                if (x, y, z) == (0, 0, 0): continue
                v = (x, y, z)
                pivot = next(c for c in v if c != 0)
                inv = pow(pivot, p - 2, p) if p > 2 else 1
                key = tuple((a * inv) % p for a in v)
                if key not in seen:
                    seen.add(key)
                    pts.append(key)

    pts = pts[:N]
    n = len(pts)
    adj = [set() for _ in range(n)]
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = pts[i], pts[j]
            if (a[0]*b[0] + a[1]*b[1] + a[2]*b[2]) % p != 0:
                continue
            common = adj[i] & adj[j]
            if any(common & adj[w] for w in common):
                continue
            edges.append((i, j))
            adj[i].add(j)
            adj[j].add(i)
    return edges
