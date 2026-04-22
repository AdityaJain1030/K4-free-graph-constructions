# Family: polarity
# Catalog: er_polarity_delete_matching
# Parent: gen_008_er_polarity (delete deterministic matching on non-absolute orbit)
# Hypothesis: deleting i->i+q mod q^2 matching on non-absolute orbit drops d_max by 1, α unchanged
# Why non-VT: three-orbit structure after matching deletion; no ER(q) automorphism preserves it

def construct(N):
    """ER(q) minus a deterministic matching on non-absolute vertices."""
    q = None
    for qq in range(2, 200):
        if qq*qq + qq + 1 == N:
            if all(qq % d != 0 for d in range(2, qq)):
                q = qq
            break
    if q is None:
        return []
    p = q

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

    # absolute points: p·p = 0
    absolute = set()
    for i,pt in enumerate(pts):
        if sum(c*c for c in pt) % p == 0:
            absolute.add(i)

    non_absolute = [i for i in range(N) if i not in absolute]

    # Build ER edges
    edges_set = set()
    for i in range(N):
        for j in range(i+1,N):
            dot = sum(pts[i][k]*pts[j][k] for k in range(3)) % p
            if dot == 0:
                edges_set.add((i,j))

    # Delete matching on non-absolute: pair non_absolute[i] with non_absolute[(i+len//2)%len]
    m = len(non_absolute)
    matching = set()
    for i in range(m//2):
        u = non_absolute[i]
        v = non_absolute[(i + m//2) % m]
        if u != v:
            matching.add((min(u,v), max(u,v)))

    edges = [e for e in edges_set if e not in matching]
    return edges


if __name__ == "__main__":
    for q in [5,7,11]:
        N = q*q+q+1
        e = construct(N)
        print(f"q={q}, N={N}: {len(e)} edges")
