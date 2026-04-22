# Family: random_process
# Catalog: ramsey_greedy_triangle_shadow
# Parent: none
# Hypothesis: two-phase build at N=34..100 — triangle-free base then K4-free extension raises d_max
# Why non-VT: two-phase random process destroys all global symmetry

import random

def construct(N):
    """Two-phase Ramsey construction.
    Phase 1: greedy triangle-free (seed N*13).
    Phase 2: add edges under K4-free constraint.
    """
    rng = random.Random(N * 13)
    adj = [set() for _ in range(N)]

    def has_triangle(u, v):
        return bool(adj[u] & adj[v])

    def has_k4(u, v):
        common = adj[u] & adj[v]
        for w in common:
            for x in common:
                if x > w and x in adj[w]:
                    return True
        return False

    pairs = [(i, j) for i in range(N) for j in range(i+1, N)]
    rng.shuffle(pairs)

    # Phase 1: triangle-free
    for u, v in pairs:
        if not has_triangle(u, v):
            adj[u].add(v)
            adj[v].add(u)

    # Phase 2: add K4-free edges (triangles now OK)
    rng2 = random.Random(N * 13 + 1)
    pairs2 = [(i, j) for i in range(N) for j in range(i+1, N)
              if j not in adj[i]]
    rng2.shuffle(pairs2)
    for u, v in pairs2:
        if not has_k4(u, v):
            adj[u].add(v)
            adj[v].add(u)

    edges = [(u, v) for u in range(N) for v in adj[u] if v > u]
    return edges


if __name__ == "__main__":
    for N in [34, 50, 70, 100]:
        e = construct(N)
        print(f"N={N}: {len(e)} edges")
