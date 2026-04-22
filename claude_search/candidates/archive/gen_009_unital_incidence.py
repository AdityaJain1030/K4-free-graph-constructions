# Family: incidence_bipartite
# Catalog: unital_point_line_incidence
# Parent: none
# Hypothesis: q=3 gives N=91 bipartite graph; large independent set but d=q+1=4 on both sides
# Why non-VT: two structurally distinct orbits (unital points vs secants), Aut never swaps them

def construct(N):
    """Bipartite incidence graph of unital in PG(2, q^2).
    Vertices: unital points (q^3+1) UNION secants (q^2*(q^2-q+1)).
    Edge: (point, secant) iff point lies on secant.
    Works when N = (q^3+1) + q^2*(q^2-q+1) for prime q.
    q=2: N=9+12=21 (too small), q=3: N=28+63=91.
    """
    # Find q
    q = None
    for qq in [2, 3, 5]:
        n_pts = qq**3 + 1
        n_sec = qq**2 * (qq**2 - qq + 1)
        if n_pts + n_sec == N:
            q = qq
            break
    if q is None:
        return []

    p = q  # prime

    # F_{q^2} arithmetic: F_q[t]/(t^2 + 1) for q=3 (2 is non-residue mod 3)
    # For q=2: F_4 = F_2[t]/(t^2+t+1), but q=2 gives N=21 which is in eval range (>=30? no, 21<30)
    # So focus on q=3, N=91
    if q == 3:
        nr = 2  # t^2 = -1 = 2 mod 3

    def fmul(x, y):
        a, b = x; c, d = y
        return ((a*c + b*d*nr) % p, (a*d + b*c) % p)

    def fpow(x, n):
        r = (1, 0)
        while n:
            if n & 1: r = fmul(r, x)
            x = fmul(x, x)
            n >>= 1
        return r

    def finv(x):
        return fpow(x, p*p - 2)

    def fconj(x):
        a, b = x
        return (a, (-b) % p)

    def hform(pt1, pt2):
        """Hermitian form: sum x_i * conj(y_i)"""
        r = [0, 0]
        for xi, yi in zip(pt1, pt2):
            pr = fmul(xi, fconj(yi))
            r[0] = (r[0] + pr[0]) % p
            r[1] = (r[1] + pr[1]) % p
        return tuple(r)

    elems = [(a, b) for a in range(p) for b in range(p)]
    nonzero = [(a, b) for a, b in elems if (a, b) != (0, 0)]

    def canonical(pt):
        for i, c in enumerate(pt):
            if c != (0, 0):
                inv = finv(c)
                return tuple(fmul(inv, cc) for cc in pt)
        return None

    # All projective points of PG(2, q^2)
    seen = {}
    pg_pts = []
    for a0, b0 in elems:
        for a1, b1 in elems:
            for a2, b2 in elems:
                if (a0,b0,a1,b1,a2,b2) == (0,0,0,0,0,0):
                    continue
                cp = canonical(((a0,b0),(a1,b1),(a2,b2)))
                if cp not in seen:
                    seen[cp] = len(pg_pts)
                    pg_pts.append(cp)

    # Unital: points with x^{q+1}+y^{q+1}+z^{q+1}=0
    unital = []
    for idx, pt in enumerate(pg_pts):
        val = [0, 0]
        for c in pt:
            pw = fpow(c, q+1)
            val[0] = (val[0]+pw[0]) % p
            val[1] = (val[1]+pw[1]) % p
        if val == [0, 0]:
            unital.append(idx)

    n_pts = q**3 + 1
    assert len(unital) == n_pts, f"Expected {n_pts} unital pts, got {len(unital)}"

    unital_set = set(unital)

    # Secants: lines meeting unital in q+1 points
    # Line through two unital points = secant (since any two unital pts determine a secant)
    def cross(pt1, pt2):
        """Cross product in F_{q^2}^3"""
        x1,y1,z1 = pt1; x2,y2,z2 = pt2
        def sub(a,b): return ((a[0]-b[0])%p,(a[1]-b[1])%p)
        nx = sub(fmul(y1,z2),fmul(z1,y2))
        ny = sub(fmul(z1,x2),fmul(x1,z2))
        nz = sub(fmul(x1,y2),fmul(y1,x2))
        return canonical((nx,ny,nz))

    def on_line(ln, pt):
        r = [0, 0]
        for li, pi in zip(ln, pt):
            pr = fmul(li, pi)
            r[0] = (r[0]+pr[0])%p
            r[1] = (r[1]+pr[1])%p
        return r == [0, 0]

    # Collect secants via unital pairs
    secant_dict = {}  # canonical normal -> set of unital pts on it
    for i in range(len(unital)):
        for j in range(i+1, len(unital)):
            pi = pg_pts[unital[i]]
            pj = pg_pts[unital[j]]
            ln = cross(pi, pj)
            if ln is None:
                continue
            if ln not in secant_dict:
                secant_dict[ln] = set()

    for u_idx in unital:
        pt = pg_pts[u_idx]
        for ln in secant_dict:
            if on_line(ln, pt):
                secant_dict[ln].add(u_idx)

    secants = {ln: s for ln, s in secant_dict.items() if len(s) == q+1}
    secant_list = list(secants.keys())
    n_sec = q**2 * (q**2 - q + 1)
    assert len(secant_list) == n_sec, f"Expected {n_sec} secants, got {len(secant_list)}"

    # Build bipartite graph: unital pts [0..n_pts-1], secants [n_pts..N-1]
    edges = []
    for s_idx, ln in enumerate(secant_list):
        for u_local, u_global in enumerate(unital):
            if u_global in secants[ln]:
                edges.append((u_local, n_pts + s_idx))

    return edges


if __name__ == "__main__":
    e = construct(91)
    print(f"N=91: {len(e)} edges")
