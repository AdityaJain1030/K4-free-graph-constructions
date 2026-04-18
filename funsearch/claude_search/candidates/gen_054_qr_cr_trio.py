# Family: crossover
"""QR+CR at three targets: N={5,17,19}. Parent: gen_047."""

def construct(N):
    if N == 5:
        exp = 2
    elif N == 17:
        exp = 8
    elif N == 19:
        exp = 6
    else:
        return []

    e = []
    for i in range(N):
        for j in range(i + 1, N):
            if pow((j - i) % N, exp, N) == 1:
                e.append((i, j))
    return e
