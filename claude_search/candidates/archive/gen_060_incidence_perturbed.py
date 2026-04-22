# Family: two_orbit
# Catalog: two_orbit_bipartite_point_line
# Parent: gen_013_incidence_graph (perturb bipartite incidence with extra K4-free edges to break IS structure)
# Hypothesis: adding cross-edges to bipartite incidence graph breaks N/2 IS; reduces α
# Why non-VT: original bipartite structure + random cross-edges destroy all Aut symmetry

import random

def construct(N):
    # AG(2,q): affine plane, points = Z_q x Z_q, lines = (slope,intercept) sets
    q = 2
    while q*q + q*q <= N: q += 1
    while q*q + q*q > N: q -= 1
    if q < 4: return []  # need N = 2*q²

    # q² points + q² lines, alternately embed in N vertices
    pts = [(i,j) for i in range(q) for j in range(q)]
    lines = []
    # Lines with slope m: {(x, m*x+b mod q) | x=0..q-1} for m in 0..q-1, b in 0..q-1
    for m in range(q):
        for b in range(q):
            lines.append(frozenset((x, (m*x+b) % q) for x in range(q)))
    # Vertical lines: {(c, y) | y=0..q-1} for c in 0..q-1
    for c in range(q):
        lines.append(frozenset((c, y) for y in range(q)))
    # Use first q² lines only
    lines = lines[:q*q]

    pt_idx = {p: i for i, p in enumerate(pts)}
    ln_idx = {l: q*q + i for i, l in enumerate(lines)}

    adj = [set() for _ in range(N)]

    # Bipartite incidence edges
    for p in pts:
        for ln in lines:
            if p in ln:
                u, v = pt_idx[p], ln_idx[ln]
                if u < N and v < N:
                    adj[u].add(v); adj[v].add(u)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Add K4-free edges within point set (breaking bipartite structure → reduces IS)
    rng = random.Random(N * 199 + 37)
    pt_pairs = [(pt_idx[pts[i]], pt_idx[pts[j]]) for i in range(len(pts)) for j in range(i+1, len(pts))]
    rng.shuffle(pt_pairs)
    cap = q + 2
    for u, v in pt_pairs[:N*2]:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
