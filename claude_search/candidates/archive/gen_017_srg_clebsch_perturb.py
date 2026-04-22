# Family: srg_perturb
# Catalog: srg_clebsch_minus_matching
# Parent: none
# Hypothesis: Clebsch(16) minus a non-orbit-invariant matching at N=16 gives non-VT K4-free
# Why non-VT: Clebsch is VT but matching deletion at indices {0,1} breaks transitivity

def _clebsch():
    """Clebsch graph: 16 vertices, degree 5, triangle-free."""
    # Vertices: {0,1}^4 quotiented by complement, i.e. pairs {v, ~v} where ~v = 15-v (XOR 15)
    # Actually use 16-vertex half-Clebsch: vertices = F_2^4, edges = Hamming dist 1 or 2
    # This gives a 10-regular graph on 16 vertices, not 5-regular.
    # Use correct construction: vertices = Z_16, edge iff i-j ∈ {1,2,4,8,5,10,3,6,12,9} mod 16?
    # Better: use the 5-dimensional construction
    # Clebsch = Cayley(Z_2^4, {e1,e2,e3,e4, e1+e2+e3+e4}) - 5-regular, triangle-free
    edges = []
    for v in range(16):
        for s in [1, 2, 4, 8, 15]:  # standard generators in Z_2^4 + all-ones
            u = v ^ s
            if u > v:
                edges.append((v, u))
    return edges

def construct(N):
    if N not in range(16, 50):
        return []

    base_edges = _clebsch()
    adj = [set() for _ in range(16)]
    for u, v in base_edges:
        adj[u].add(v); adj[v].add(u)

    # For N=16: return Clebsch minus matching {(0,15),(1,14),(2,13),(3,12)}
    if N == 16:
        matching = {(0,15),(1,14),(2,13),(3,12)}
        return [(u,v) for u,v in base_edges if (u,v) not in matching and (v,u) not in matching]

    # For N=40: embed Clebsch in extended graph with 24 extra vertices
    # Add 24 extra vertices (16..39), connected to original vertices via hash rule, K4-free checked
    if N == 40:
        full_adj = [set() for _ in range(40)]
        for u,v in base_edges:
            full_adj[u].add(v); full_adj[v].add(u)

        def has_k4(u, v):
            common = list(full_adj[u] & full_adj[v])
            for a in range(len(common)):
                for b in range(a+1, len(common)):
                    if common[b] in full_adj[common[a]]:
                        return True
            return False

        for ext in range(16, 40):
            for base in range(16):
                h = (ext * 97 + base * 37) % 5
                if h == 0 and not has_k4(ext, base):
                    full_adj[ext].add(base); full_adj[base].add(ext)

        return [(u,v) for u in range(40) for v in full_adj[u] if v > u]

    return []
