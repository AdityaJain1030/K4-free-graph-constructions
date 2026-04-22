# Family: two_orbit
# Catalog: two_orbit_bipartite_point_line
# Parent: gen_013_incidence_graph (use Latin square structure instead of projective plane)
# Hypothesis: LS_2(q) srg-like graph is K4-free for specific params; α smaller than bipartite
# Why non-VT: asymmetric row/column perturbation breaks the full symmetric group action

import random

def construct(N):
    # Latin square graph LS(q,q): N = q^2, edges from shared row OR column
    # But these have triangles. Instead build anti-Latin square (complement-like)
    # Try: random q×q Latin square, then connect cells that share row XOR column but not both
    q = 2
    while (q+1)*(q+1) <= N: q += 1
    # Use q×q grid: N = q^2 cells (i,j)
    n2 = q*q
    if n2 < 34 or n2 > 200: return []

    adj = [set() for _ in range(n2)]
    def cell(i,j): return i*q+j

    # Connect cells in same row: (i,j) ~ (i,k) for j≠k - but NOT same column
    # This gives row-cliques of size q; K4 occurs when q≥4 (4 cells in same row)
    # Instead: K4-free graph based on mixed row/column adjacency
    # Edge (i,j)~(i',j') iff (i=i' XOR j=j') - this is the "rook graph" complement
    # Actually let's use: edge iff exactly one of (row match, col match)

    for i in range(q):
        for j in range(q):
            for i2 in range(q):
                for j2 in range(q):
                    if (i,j) >= (i2,j2): continue
                    same_row = (i == i2)
                    same_col = (j == j2)
                    if same_row ^ same_col:  # XOR: exactly one match
                        u, v = cell(i,j), cell(i2,j2)
                        adj[u].add(v); adj[v].add(u)

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    # Remove K4 edges
    changed = True
    while changed:
        changed = False
        for u in range(n2):
            for v in list(adj[u]):
                if v <= u: continue
                if has_k4(u, v):
                    adj[u].discard(v); adj[v].discard(u); changed=True; break
            if changed: break

    # Add random K4-free edges
    rng = random.Random(N * 167 + 89)
    non_edges = [(i,j) for i in range(n2) for j in range(i+1,n2) if j not in adj[i]]
    rng.shuffle(non_edges)
    cap = q + 2
    for u, v in non_edges:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(n2) for v in adj[u] if v > u]
