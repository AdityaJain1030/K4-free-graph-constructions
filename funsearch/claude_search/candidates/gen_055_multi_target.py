# Family: crossover
"""Hybrid: circulant at N=8, QR at N=17, CR at N=19. Parent: gen_047."""

def construct(N):
    if N == 8:
        e = []
        for i in range(8):
            for k in [1, 2]:
                j = (i + k) % 8
                a, b = (i, j) if i < j else (j, i)
                e.append((a, b))
        return e
    elif N == 17 or N == 19:
        exp = (N - 1) // (2 if N == 17 else 3)
        e = []
        for i in range(N):
            for j in range(i + 1, N):
                if pow((j - i) % N, exp, N) == 1:
                    e.append((i, j))
        return e
    return []
