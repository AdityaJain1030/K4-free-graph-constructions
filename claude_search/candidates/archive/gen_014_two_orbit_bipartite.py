# Family: incidence_bipartite
# Catalog: two_orbit_bipartite_point_line
# Parent: none
# Hypothesis: PG(2,q) point-line incidence bipartite graph at N=2*(q^2+q+1) for q=5,7
# Why non-VT: two structurally distinct sides (points vs lines); Aut never swaps them

def construct(N):
    """Point-line incidence graph of PG(2,q). N = 2*(q^2+q+1)."""
    q = None
    for qq in range(2, 50):
        if 2*(qq*qq+qq+1) == N:
            if all(qq % d != 0 for d in range(2, qq)):
                q = qq
            break
    if q is None:
        return []
    p = q
    m = q*q + q + 1  # number of points = number of lines

    # Points of PG(2,q)
    seen = {}
    pts = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if (x,y,z) == (0,0,0): continue
                if x != 0:
                    iv = pow(x,p-2,p)
                    rep = (1,(y*iv)%p,(z*iv)%p)
                elif y != 0:
                    iv = pow(y,p-2,p)
                    rep = (0,1,(z*iv)%p)
                else:
                    rep = (0,0,1)
                if rep not in seen:
                    seen[rep] = len(pts)
                    pts.append(rep)

    # Lines of PG(2,q) = dual points (same set by duality)
    # Edge: point i ~ line j iff pts[i] · lines[j] = 0 (incidence)
    # Lines = same canonical reps (PG(2,q) is self-dual)
    lines = pts  # same set

    edges = []
    for i, pt in enumerate(pts):
        for j, ln in enumerate(lines):
            dot = sum(pt[k]*ln[k] for k in range(3)) % p
            if dot == 0:
                edges.append((i, m + j))  # point i ~ line m+j

    return edges


if __name__ == "__main__":
    for q in [3, 5, 7]:
        N = 2*(q*q+q+1)
        e = construct(N)
        print(f"q={q}, N={N}: {len(e)} edges")
