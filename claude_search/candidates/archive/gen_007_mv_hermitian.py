# Family: hermitian_pencil
# Catalog: mv_hermitian
# Parent: none
# Hypothesis: q=3 gives N=63 — medium size where α≈q^{4/3}(log q)^{4/3} should give c near 1.0
# Why non-VT: random per-pencil bipartition creates 3 orbits with no global automorphism

import random
from itertools import combinations

def construct(N):
    """Mattheus-Verstraete Hq* construction at q=3 (N=63).
    Vertices = secants of the Hermitian unital in PG(2,9).
    Edges: two secants adjacent iff they share a unital point, with per-pencil bipartition.
    """
    # Find q such that q^2*(q^2-q+1) == N
    q = None
    for qq in [2, 3, 5]:
        if qq*qq*(qq*qq - qq + 1) == N:
            q = qq
            break
    if q is None:
        return []

    # Build F_{q^2} as polynomials mod irreducible over F_q
    # For q=3: F_9 = F_3[t]/(t^2+1) (t^2=-1=2 mod 3, check: 2 is non-residue mod 3 since 1^2=1,2^2=1)
    # Actually check: squares mod 3 are {0,1}, so 2 is non-residue. t^2 + 1 = 0 => t^2 = -1 = 2.
    # Elements of F_9: (a + b*t) for a,b in F_3
    p = q  # q is prime

    def fq2_mul(x, y):
        # x = (a,b), y = (c,d), product in F_{q^2} = F_q[t]/(t^2 - nr) where nr is non-residue
        # For q=3: t^2 = 2 (since t^2+1=0 => t^2=-1=2)
        # (a+bt)(c+dt) = ac + (ad+bc)t + bd*t^2 = (ac + bd*nr) + (ad+bc)t
        if q == 2:
            nr = 1  # t^2+t+1=0, but let's use t^2=t+1 for F_4
            # Actually for q=2: non-residue? F_2 has only 0,1; t^2+t+1 irreducible
            # Use t^2 = t+1 => t^2+t+1=0
            a, b = x; c, d = y
            ac = (a*c) % 2
            ad_bc = (a*d + b*c) % 2
            bd = (b*d) % 2
            # t^2 = t+1, so bd*t^2 = bd*(t+1) = bd + bd*t
            return ((ac + bd) % 2, (ad_bc + bd) % 2)
        else:
            nr = p - 1  # -1 mod p; for q=3: nr=2
            a, b = x; c, d = y
            return ((a*c + b*d*nr) % p, (a*d + b*c) % p)

    def fq2_conj(x):
        # Frobenius: x^q = (a+bt)^q = a^q + b^q * t^q = a + b*t^q
        # t^q: for q=3, t^3 = t*t^2 = t*2 = 2t => t^q = (p-1)*t = -t
        # conj(a,b) = (a, -b mod p)
        a, b = x
        if q == 2:
            # t^2 = t+1 => t^q = t^2 = t+1... this gets complex, skip q=2 here
            return (a, b)
        return (a % p, (-b) % p)

    def fq2_hermitian_form(x, y):
        # <x, y> = x0*conj(y0) + x1*conj(y1) + x2*conj(y2) for projective points
        # Returns element of F_q (the "trace form" maps to F_q)
        result = [0, 0]
        for xi, yi in zip(x, y):
            cy = fq2_conj(yi)
            prod = fq2_mul(xi, cy)
            result[0] = (result[0] + prod[0]) % p
            result[1] = (result[1] + prod[1]) % p
        return result

    def is_fq_element(x):
        return x[1] == 0

    # Build all points of PG(2, q^2): equivalence classes in F_{q^2}^3 \ {0}
    # Canonical rep: first nonzero coordinate is (1,0) [i.e., = 1 in F_{q^2}]
    elements_fq2 = [(a, b) for a in range(p) for b in range(p)]
    nonzero_fq2 = [(a, b) for a, b in elements_fq2 if (a, b) != (0, 0)]

    def fq2_scalar_mul(s, x):
        return fq2_mul(s, x)

    def canonical_point(pt):
        # pt is a triple of F_{q^2} elements
        # Find first nonzero, scale so it's (1,0)
        for i, coord in enumerate(pt):
            if coord != (0, 0):
                # Need inverse of coord
                # inv: a^{-1} in F_{q^2}
                # Use Fermat: inv = coord^{q^2-2}
                inv = _fq2_inv(coord)
                return tuple(fq2_mul(inv, c) for c in pt)
        return None

    def _fq2_inv(x):
        # x^{q^2-2} by repeated squaring
        n = p*p - 2
        result = (1, 0)
        base = x
        while n:
            if n & 1:
                result = fq2_mul(result, base)
            base = fq2_mul(base, base)
            n >>= 1
        return result

    # Generate all projective points of PG(2, q^2)
    # (q^2)^3 - 1 nonzero vectors / (q^2 - 1) scalar classes = q^4 + q^2 + 1 points
    all_triples = []
    for a0, b0 in elements_fq2:
        for a1, b1 in elements_fq2:
            for a2, b2 in elements_fq2:
                if (a0, b0, a1, b1, a2, b2) != (0, 0, 0, 0, 0, 0):
                    all_triples.append(((a0,b0),(a1,b1),(a2,b2)))

    seen = {}
    pg2q2_pts = []
    for pt in all_triples:
        cp = canonical_point(pt)
        if cp not in seen:
            seen[cp] = len(pg2q2_pts)
            pg2q2_pts.append(cp)

    # Find unital H: points with x^{q+1} + y^{q+1} + z^{q+1} = 0
    def fq2_pow(x, n):
        result = (1, 0)
        base = x
        while n:
            if n & 1:
                result = fq2_mul(result, base)
            base = fq2_mul(base, base)
            n >>= 1
        return result

    unital = []
    for pt in pg2q2_pts:
        val = [0, 0]
        for coord in pt:
            pw = fq2_pow(coord, q+1)
            val[0] = (val[0] + pw[0]) % p
            val[1] = (val[1] + pw[1]) % p
        if val == [0, 0]:
            unital.append(seen[pt])

    # Build lines of PG(2, q^2) and find secants (lines meeting unital in q+1 points)
    # A line in PG(2,q^2) is determined by a normal vector n: {x : n·x = 0}
    # Two points determine a unique line
    unital_set = set(unital)

    # Build incidence: for each pair of unital points, their line is a secant
    # Secants are lines that meet H in exactly q+1 points
    # Strategy: enumerate lines through pairs of unital points; keep unique ones

    def line_through(p1, p2):
        # Normal vector = p1 × p2 (cross product in F_{q^2}^3)
        x1, y1, z1 = p1
        x2, y2, z2 = p2
        # n = p1 × p2
        def sub(a, b):
            return ((a[0]-b[0]) % p, (a[1]-b[1]) % p)
        def neg(a):
            return ((-a[0]) % p, (-a[1]) % p)
        nx = sub(fq2_mul(y1,z2), fq2_mul(z1,y2))
        ny = sub(fq2_mul(z1,x2), fq2_mul(x1,z2))
        nz = sub(fq2_mul(x1,y2), fq2_mul(y1,x2))
        return canonical_point((nx, ny, nz))

    def dot(n, pt):
        r = [0, 0]
        for ni, pi in zip(n, pt):
            pr = fq2_mul(ni, pi)
            r[0] = (r[0] + pr[0]) % p
            r[1] = (r[1] + pr[1]) % p
        return r

    # Find all secants
    secant_lines = {}  # normal_vec -> list of unital points on it
    for i in range(len(unital)):
        for j in range(i+1, len(unital)):
            pi = pg2q2_pts[unital[i]]
            pj = pg2q2_pts[unital[j]]
            ln = line_through(pi, pj)
            if ln not in secant_lines:
                secant_lines[ln] = set()

    # For each secant, find all unital points on it
    for u_idx in unital:
        pt = pg2q2_pts[u_idx]
        for ln in secant_lines:
            if dot(ln, pt) == [0, 0]:
                secant_lines[ln].add(u_idx)

    # Keep only lines with exactly q+1 unital points
    secants = {ln: pts for ln, pts in secant_lines.items() if len(pts) == q+1}
    secant_list = list(secants.keys())

    if len(secant_list) != N:
        return []

    # For each unital point, find which secants pass through it (pencil)
    pencil = {}  # unital_point -> list of secant indices
    for s_idx, ln in enumerate(secant_list):
        for u_idx in secants[ln]:
            if u_idx not in pencil:
                pencil[u_idx] = []
            pencil[u_idx].append(s_idx)

    # Build Hq: two secants adjacent iff they share a unital point
    # Then Hq*: for each pencil, random bipartition, replace clique with K_{A,B}
    rng = random.Random(N * 17 + 3)
    side = [None] * N  # 0 or 1 for each secant

    for u_idx, pen in pencil.items():
        A = []
        B = []
        for s_idx in pen:
            bit = rng.randint(0, 1)
            if bit == 0:
                A.append(s_idx)
            else:
                B.append(s_idx)
        # Assign sides (only first time each secant is seen)
        for s_idx in A:
            if side[s_idx] is None:
                side[s_idx] = (u_idx, 0)
        for s_idx in B:
            if side[s_idx] is None:
                side[s_idx] = (u_idx, 1)

    edges = set()
    for u_idx, pen in pencil.items():
        A = [s for s in pen if side[s] is not None and side[s][1] == 0]
        B = [s for s in pen if side[s] is not None and side[s][1] == 1]
        # Fallback: use rng-based assignment per pencil
        rng2 = random.Random(u_idx * 31 + N)
        A2 = []
        B2 = []
        for s in pen:
            if rng2.randint(0, 1) == 0:
                A2.append(s)
            else:
                B2.append(s)
        for a in A2:
            for b in B2:
                if a != b:
                    edges.add((min(a,b), max(a,b)))

    return list(edges)


if __name__ == "__main__":
    edges = construct(63)
    print(f"N=63: {len(edges)} edges")
    edges2 = construct(12)
    print(f"N=12: {len(edges2)} edges")
