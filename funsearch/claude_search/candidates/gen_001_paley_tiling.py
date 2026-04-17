"""Tile disjoint copies of the Paley graph P(17).

P(17) is the Cayley graph on Z/17Z with connection set = quadratic residues mod 17.
It is K4-free, 8-regular, alpha=3 => c = 3*8/(17*ln 8) ~ 0.6789.
Extra vertices are left isolated (they hurt c since d_max=8 still, alpha grows).
"""


def construct(N):
    p = 17
    qr = {(x * x) % p for x in range(1, p)}
    edges = []
    blocks = N // p
    for b in range(blocks):
        base = b * p
        for i in range(p):
            for j in range(i + 1, p):
                if (j - i) % p in qr:
                    edges.append((base + i, base + j))
    return edges
