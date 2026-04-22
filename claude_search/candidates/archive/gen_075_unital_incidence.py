# Family: two_orbit
# Catalog: unital_point_line_incidence
# Hypothesis: bipartite unital incidence for q=2 (N=21) and q=3 (N=91); K4-free by bipartiteness
# Why non-VT: two structurally distinct orbits (unital points vs secants); aut never swaps them

def construct(N):
    # q=2: unital in PG(2,4); |H|=9 points, 12 secants, N=21 (too small for eval)
    # q=3: unital in PG(2,9); |H|=28 points, 63 secants, N=91
    if N == 21: q = 2
    elif N == 91: q = 3
    else: return []

    # Build GF(q^2) as GF(q)[t]/(t^2 + non-residue)
    # For q=2: GF(4) = GF(2)[t]/(t^2+t+1), for q=3: GF(9) = GF(3)[t]/(t^2+1)
    if q == 2:
        # GF(4): elements 0,1,t,t+1 with t^2=t+1
        def mul(a, b):  # a,b in {0,1,2,3} = {0, 1, t, t+1}
            # represent as (a0,a1) in GF(2)^2
            aa = (a & 1, (a >> 1) & 1); bb = (b & 1, (b >> 1) & 1)
            r0 = (aa[0]*bb[0] + aa[1]*bb[1]) % 2
            r1 = (aa[0]*bb[1] + aa[1]*bb[0] + aa[1]*bb[1]) % 2
            return r0 + 2*r1
        def conj(a):
            aa = (a & 1, (a >> 1) & 1); return aa[0] + 2*((aa[0]+aa[1]) % 2)
        def norm(a): return mul(a, conj(a)) & 1  # norm is in GF(2)={0,1}
        q2 = 4
    else:
        # GF(9): elements (a0+a1*t) with t^2=2 (=-1 in GF(3))
        def mul(a, b):
            a0, a1 = a % 3, a // 3; b0, b1 = b % 3, b // 3
            return (a0*b0 + 2*a1*b1) % 3 + 3*((a0*b1 + a1*b0) % 3)
        def conj(a): return a % 3 + 3*((-a // 3) % 3)
        def norm(a): return (mul(a, conj(a))) % 3  # norm in GF(3)
        q2 = 9

    # Points of PG(2, q^2): canonical triples, first nonzero coord = 1
    nonzero = [x for x in range(1, q2)]
    def inv(a):
        for b in nonzero:
            if mul(a, b) % (1 if q == 2 else 3) == 1 and mul(a, b) // (1 if q == 2 else 3) == 0:
                pass
        # Simpler: brute force
        for b in range(1, q2):
            if mul(a, b) == 1: return b
        return None

    def canonical(x, y, z):
        for v in [x, y, z]:
            if v != 0:
                iv = inv(v)
                return (mul(x, iv), mul(y, iv), mul(z, iv))
        return None

    seen = set(); pts = []; secants = []
    for x in range(q2):
        for y in range(q2):
            for z in range(q2):
                if x == y == z == 0: continue
                can = canonical(x, y, z)
                if can and can not in seen:
                    seen.add(can); pts.append(can)

    # Hermitian unital: norm(x)+norm(y)+norm(z) = 0 in GF(q)
    qmod = 2 if q == 2 else 3
    H_pts = [i for i, (x, y, z) in enumerate(pts)
             if (norm(x) + norm(y) + norm(z)) % qmod == 0]

    # Lines of PG(2,q^2): for each triple (a,b,c) canonical, line = {(x,y,z): ax+by+cz=0 in GF(q^2)}
    # Secants: lines meeting H in exactly q+1 points
    seen_lines = set(); all_lines = []
    for a in range(q2):
        for b in range(q2):
            for c in range(q2):
                if a == b == c == 0: continue
                can = canonical(a, b, c)
                if can and can not in seen_lines:
                    seen_lines.add(can); all_lines.append(can)

    def dot_gf(p, l):
        # inner product in GF(q^2): p[0]*l[0] + p[1]*l[1] + p[2]*l[2]
        s = 0
        for i in range(3):
            t = mul(p[i], l[i])
            # add in GF(q^2)
            s0, s1 = s % q2, 0  # This is wrong; need proper GF(q^2) addition
        pass

    # GF(q^2) addition: component-wise mod q
    def add_gf(a, b): return (a % qmod + b % qmod) % qmod + qmod * ((a // qmod + b // qmod) % qmod)

    def dot_gfq2(p, l):
        s = 0
        for i in range(3):
            t = mul(p[i], l[i])
            s = add_gf(s, t)
        return s

    secants_list = [l for l in all_lines
                    if sum(1 for h in H_pts if dot_gfq2(pts[h], l) == 0) == q+1]

    nH = len(H_pts); nS = len(secants_list)
    if nH + nS != N: return []

    adj = [set() for _ in range(N)]
    for si, l in enumerate(secants_list):
        for hi, h in enumerate(H_pts):
            if dot_gfq2(pts[h], l) == 0:
                adj[hi].add(nH + si); adj[nH + si].add(hi)

    return [(u, v) for u in range(N) for v in adj[u] if v > u]
