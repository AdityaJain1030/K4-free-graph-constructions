# Family: cayley_cyclic
"""Cubic residues mod p for primes ≡ 1 mod 3."""

def construct(N):
    # Primes ≡ 1 mod 3 (have cubic residues)
    if N not in (7, 13, 19, 31, 37, 43):
        return []

    edges = []
    for i in range(N):
        for j in range(i+1, N):
            diff = (j - i) % N
            cr = pow(diff, (N-1)//3, N)
            if cr == 1:
                edges.append((i, j))

    return edges
