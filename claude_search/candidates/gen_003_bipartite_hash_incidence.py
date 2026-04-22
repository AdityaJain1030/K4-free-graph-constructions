# Family: two_orbit
# Parent: none
# Hypothesis: A bipartite graph with left part L of size a = N//3 and right
#   part R of size N - a, with edges defined by a fixed non-symmetric hash
#   rule over (i, j). Bipartite graphs are trivially K4-free (no triangles).
#   Left and right parts have structurally different roles (different sizes,
#   asymmetric hash), giving clean two-orbit structure. The construction
#   provides a starting point for mutations where intra-part edges or a
#   second hash layer are added.
# Why non-VT: the hash rule treats the two parts asymmetrically (i * 7 vs
#   j * 11), the parts have different sizes, and no automorphism swaps L
#   and R. Degree distribution within each part is non-uniform because the
#   hash does not factor as f(i) + g(j).

def construct(N):
    if N < 10:
        return []
    a = N // 3
    b = N - a
    edges = []
    for i in range(a):
        for j in range(b):
            h = (i * 7 + j * 11 + (i * j) % 13) % 17
            if h < 6:
                edges.append((i, a + j))
    return edges
