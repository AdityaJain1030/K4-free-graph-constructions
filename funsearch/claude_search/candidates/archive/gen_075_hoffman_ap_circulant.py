import math

def construct(N):
    """For each N, pick the AP circulant {r,r+d,...} minimizing Hoffman bound on alpha.
    AP offsets have diffs = multiples of d, not in S (since S ≡ r mod d, r≠0 mod d) => K4-free."""
    best_hc = float('inf')
    best_S = [2, 3, 5]

    for d in range(1, min(N // 2, 30)):
        for r in range(1, d):
            for k in range(2, 8):
                S = [r + i * d for i in range(k)]
                if S[-1] >= N // 2:
                    break
                deg = 2 * k
                lam_min = min(
                    sum(2 * math.cos(2 * math.pi * j * s / N) for s in S)
                    for j in range(1, N)
                )
                if lam_min >= 0:
                    continue
                hc = (-lam_min) * deg / ((deg - lam_min) * math.log(deg))
                if hc < best_hc:
                    best_hc = hc
                    best_S = S

    seen = set()
    edges = []
    for i in range(N):
        for s in best_S:
            for j in [(i + s) % N, (i - s) % N]:
                key = (min(i, j), max(i, j))
                if key not in seen and key[0] != key[1]:
                    seen.add(key)
                    edges.append(key)
    return edges
