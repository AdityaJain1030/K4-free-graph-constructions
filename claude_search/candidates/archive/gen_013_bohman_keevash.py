# Family: random_process
# Catalog: bohman_keevash_k4_process
# Parent: none
# Hypothesis: K4-free greedy process at N=34..100 gives d_max=O(sqrt(N log N)); baseline measurement
# Why non-VT: random edge order destroys global symmetry almost surely for N >= 10

import random

def construct(N):
    """K4-free random greedy process. Seed = N*31+7."""
    rng = random.Random(N * 31 + 7)
    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = adj[u] & adj[v]
        c = list(common)
        for i in range(len(c)):
            for j in range(i+1, len(c)):
                if c[j] in adj[c[i]]:
                    return True
        return False

    pairs = [(i, j) for i in range(N) for j in range(i+1, N)]
    rng.shuffle(pairs)
    for u, v in pairs:
        if not has_k4(u, v):
            adj[u].add(v)
            adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]


if __name__ == "__main__":
    for N in [34, 50, 70, 100]:
        e = construct(N)
        dmax = max((sum(1 for u,v in e if u==i or v==i) for i in range(N)), default=0)
        print(f"N={N}: {len(e)} edges, d_max={dmax}")
