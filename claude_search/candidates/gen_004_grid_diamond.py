# Family: invented
# Parent: none
# Hypothesis: A 2D integer-lattice grid graph carved into a diamond (rhombus)
#   region. Edges connect lattice neighbors only. Grid graphs are planar
#   and bipartite — triangle-free, hence K4-free. The diamond boundary
#   creates three degree classes (corners with degree 2, boundary with
#   degree 3, interior with degree 4). Sparse (max degree 4), so c is
#   bounded below by α / (N · ln 4) · 4; alpha is N/2 (bipartite), so
#   this seed is not meant to beat the threshold — it is a structural
#   exemplar for the agent to mutate by densifying, adding diagonals,
#   or combining with other pieces.
# Why non-VT: corners, boundary edges, and interior vertices have different
#   degrees — three distinct orbits under any automorphism. The diamond
#   shape rules out translation symmetry.

def construct(N):
    if N < 7 or N > 200:
        return []
    k = 1
    while k * k < N:
        k += 1
    # Place lattice points (r, c) in a diamond: |r| + |c| <= k - 1
    positions = []
    for s in range(k):
        for r in range(-s, s + 1):
            c = s - abs(r)
            positions.append((r, c))
            if c != -c:
                positions.append((r, -c))
            if len(positions) >= N:
                break
        if len(positions) >= N:
            break
    positions = positions[:N]
    idx = {p: i for i, p in enumerate(positions)}
    edges = set()
    for (r, c), i in idx.items():
        for dr, dc in ((1, 0), (0, 1)):
            nb = (r + dr, c + dc)
            if nb in idx:
                j = idx[nb]
                edges.add((min(i, j), max(i, j)))
    return list(edges)
