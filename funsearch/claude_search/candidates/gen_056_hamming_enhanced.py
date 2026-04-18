# Family: hamming
"""Enhanced Hamming: connect vertices at distance 1 or k-1 in hypercube."""

def construct(N):
    if N & (N - 1) == 0 and N > 1:
        k = (N - 1).bit_length()
        if 2 ** k != N:
            return []
    else:
        return []

    edges = []
    for i in range(N):
        for j in range(i + 1, N):
            hd = bin(i ^ j).count('1')
            if hd == 1 or hd == k - 1:
                edges.append((i, j))

    return edges
