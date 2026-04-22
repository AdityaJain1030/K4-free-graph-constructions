# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: none
# Hypothesis: 3-layer lift of ER(5) base (N=31) with non-uniform hash cross-edges, total N=93
# Why non-VT: non-uniform cross-edges break layer-cycling automorphism; ER(5) base is non-VT

def construct(N):
    """Asymmetric layer lift of ER(q) base.
    Base graph = ER(5) on m=31 vertices. Use k = N // 31 layers.
    Cross-edges: only adjacent layers i->i+1, via deterministic hash.
    K4-freeness guarded by on-the-fly check.
    """
    # Build ER(q) base
    def build_er(q):
        """ER(q) polarity graph on q^2+q+1 vertices."""
        p = q
        seen = {}
        pts = []
        for x in range(q):
            for y in range(q):
                for z in range(q):
                    if (x, y, z) == (0, 0, 0):
                        continue
                    if x != 0:
                        iv = pow(x, p-2, p)
                        rep = (1, (y*iv)%p, (z*iv)%p)
                    elif y != 0:
                        iv = pow(y, p-2, p)
                        rep = (0, 1, (z*iv)%p)
                    else:
                        rep = (0, 0, 1)
                    if rep not in seen:
                        seen[rep] = len(pts)
                        pts.append(rep)
        edges = []
        n = len(pts)
        for i in range(n):
            for j in range(i+1, n):
                dot = sum(pts[i][k]*pts[j][k] for k in range(3)) % p
                if dot == 0:
                    edges.append((i, j))
        return n, edges

    base_q = 5  # N=31
    m, base_edges = build_er(base_q)
    if N % m != 0 or N // m < 2:
        # Try q=3 (N=13) or q=7 (N=57)
        for bq in [3, 7]:
            bm, be = build_er(bq)
            if N % bm == 0 and N // bm >= 2:
                m, base_edges = bm, be
                break
        else:
            # Fallback: just use any k*m near N
            # Find best fit
            best = None
            for bq in [3, 5, 7, 11]:
                bm = bq*bq + bq + 1
                k = N // bm
                if k >= 2 and k*bm <= N:
                    best = (bm, bq, k)
                    break
            if best is None:
                return []
            m, best_q, k = best
            _, base_edges = build_er(best_q)

    k = N // m
    total = k * m

    # Build adjacency for quick K4 check
    adj = [set() for _ in range(total)]
    for layer in range(k):
        offset = layer * m
        for u, v in base_edges:
            adj[offset+u].add(offset+v)
            adj[offset+v].add(offset+u)

    def has_k4(u, v):
        """Would adding edge u-v create K4? Check if any w,x are neighbors of both u and v."""
        common = adj[u] & adj[v]
        c_list = list(common)
        for i in range(len(c_list)):
            for j in range(i+1, len(c_list)):
                if c_list[j] in adj[c_list[i]]:
                    return True
        return False

    edges_out = list(base_edges[:])
    # Remap base edges to include all layers
    edges_out = []
    for layer in range(k):
        offset = layer * m
        for u, v in base_edges:
            edges_out.append((offset+u, offset+v))

    # Cross-layer edges: between layer i and i+1 (mod k)
    # Use hash-based rule: include (layer_i vertex u, layer_{i+1} vertex v) iff
    # hash(u * 1009 + v * 7 + layer * 997) % 5 == 0
    for layer in range(k):
        next_layer = (layer + 1) % k
        offset_a = layer * m
        offset_b = next_layer * m
        for u in range(m):
            for v in range(m):
                h = (u * 1009 + v * 7 + layer * 997) % 11
                if h == 0:
                    a, b = offset_a + u, offset_b + v
                    if b not in adj[a] and not has_k4(a, b):
                        adj[a].add(b)
                        adj[b].add(a)
                        edges_out.append((min(a,b), max(a,b)))

    # Trim to N vertices if total > N
    if total > N:
        edges_out = [(u, v) for u, v in edges_out if u < N and v < N]

    return edges_out


if __name__ == "__main__":
    for N in [62, 93, 57]:
        e = construct(N)
        print(f"N={N}: {len(e)} edges")
