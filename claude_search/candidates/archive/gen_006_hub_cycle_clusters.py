# Family: core_periphery
# Parent: none
# Hypothesis: k hub vertices arranged in a cycle C_k (k >= 4) with a
#   non-uniform set of leaf pendants attached to each hub. Hub i receives
#   (i mod 3) + 1 leaves, so hubs have varying degrees and leaves have
#   degree 1. K4-free because C_k (k >= 4) is triangle-free and leaves
#   add no triangles. Dense variants could replace C_k with a denser
#   triangle-free core; the seed demonstrates the core-periphery split.
# Why non-VT: leaves have degree 1, hubs have degree 2 + leaf_count ≥ 3 —
#   different degree classes, at least two orbits. Hubs with different
#   leaf counts are further distinguishable, so the automorphism group
#   is small and non-transitive.

def construct(N):
    if N < 10 or N > 200:
        return []
    k = max(4, N // 4)
    if k >= N:
        return []
    edges = []
    for i in range(k):
        edges.append((i, (i + 1) % k))
    leaf = k
    hub = 0
    while leaf < N:
        target = (hub % 3) + 1
        for _ in range(target):
            if leaf >= N:
                break
            edges.append((hub % k, leaf))
            leaf += 1
        hub += 1
    return edges
