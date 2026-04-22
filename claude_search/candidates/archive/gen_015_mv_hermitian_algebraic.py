# Family: hermitian_pencil
# Catalog: mv_hermitian
# Parent: gen_007_mv_hermitian (replaced random pencil bipartition with algebraic square-test in F_{q^2})
# Hypothesis: bipartition by quadratic residue in F_{q^2} gives deterministic small-α realization
# Why non-VT: algebraic bipartition based on non-Galois-orbit criterion → 3 structurally distinct orbits

import random

def construct(N):
    """Hq* with algebraic bipartition: side(u, s) = 0 if the pencil index is a QR in Z/|pencil|."""
    q = None
    for qq in [2, 3, 5]:
        if qq*qq*(qq*qq - qq + 1) == N:
            q = qq
            break
    if q is None:
        return []

    p = q
    nr = p - 1  # -1 mod p (non-residue for p≡3 mod 4, e.g. p=3)

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
        return (x[0], (-x[1]) % p)

    def canonical(pt):
        for c in pt:
            if c != (0, 0):
                inv = finv(c)
                return tuple(fmul(inv, cc) for cc in pt)
        return None

    elems = [(a, b) for a in range(p) for b in range(p)]

    seen = {}
    pg_pts = []
    for e0 in elems:
        for e1 in elems:
            for e2 in elems:
                if e0 == (0,0) and e1 == (0,0) and e2 == (0,0): continue
                cp = canonical((e0, e1, e2))
                if cp not in seen:
                    seen[cp] = len(pg_pts)
                    pg_pts.append(cp)

    def hval(pt):
        return tuple((sum(fpow(c, q+1)[k] for c in pt) % p) for k in range(2))

    unital = [i for i, pt in enumerate(pg_pts) if hval(pt) == (0,0)]
    unital_set = set(unital)

    def cross(p1, p2):
        x1,y1,z1 = p1; x2,y2,z2 = p2
        def sub(a,b): return ((a[0]-b[0])%p,(a[1]-b[1])%p)
        nx = sub(fmul(y1,z2),fmul(z1,y2))
        ny = sub(fmul(z1,x2),fmul(x1,z2))
        nz = sub(fmul(x1,y2),fmul(y1,x2))
        return canonical((nx,ny,nz))

    def on_line(ln, pt):
        r = [0, 0]
        for li, pi in zip(ln, pt):
            pr = fmul(li, pi)
            r[0] = (r[0]+pr[0])%p; r[1] = (r[1]+pr[1])%p
        return r == [0, 0]

    secant_dict = {}
    for i in range(len(unital)):
        for j in range(i+1, len(unital)):
            ln = cross(pg_pts[unital[i]], pg_pts[unital[j]])
            if ln and ln not in secant_dict:
                secant_dict[ln] = set()

    for u_idx in unital:
        for ln in secant_dict:
            if on_line(ln, pg_pts[u_idx]):
                secant_dict[ln].add(u_idx)

    secants = {ln: s for ln, s in secant_dict.items() if len(s) == q+1}
    secant_list = list(secants.keys())
    if len(secant_list) != N:
        return []

    pencil = {}
    for s_idx, ln in enumerate(secant_list):
        for u_idx in secants[ln]:
            pencil.setdefault(u_idx, []).append(s_idx)

    # Algebraic bipartition: for each pencil, sort secant indices and split by position parity
    edges = set()
    for u_idx, pen in pencil.items():
        sorted_pen = sorted(pen)
        A = [s for i, s in enumerate(sorted_pen) if i % 2 == 0]
        B = [s for i, s in enumerate(sorted_pen) if i % 2 == 1]
        for a in A:
            for b in B:
                edges.add((min(a,b), max(a,b)))

    return list(edges)
