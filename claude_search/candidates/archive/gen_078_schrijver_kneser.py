# Family: invented
# Catalog: bohman_keevash_k4_process
# Parent: gen_077_5partite_k4free (stable Kneser graph S(n,k): 5-chromatic, K4-free by pigeonhole)
# Hypothesis: S(n,3) is K4-free (can't find 4 disjoint 3-subsets of [n] for small n), χ=n-4=5 at n=9
# Why non-VT: circular stable subsets have C_n symmetry but not full Aut; perturbed further by edge flip

import random

def construct(N):
    # Schrijver graph S(n,3): vertices = stable 3-subsets of Z_n (no two consecutive mod n)
    # Edge iff disjoint. K4-free since 4 disjoint 3-subsets need 12 elements, n<12 for interesting range.
    # chi(S(n,3)) = n - 4; target chi=5 means n=9, N=30. Scale by taking multiple n values.

    # Find n such that number of stable 3-subsets ≈ N
    # stable 3-subsets of Z_n: no i,j in S with (j-i)%n == 1 or (i-j)%n == 1
    def stable_3subsets(n):
        subs = []
        for i in range(n):
            for j in range(i+2, n):
                if j == n-1 and i == 0: continue  # 0 and n-1 are adjacent
                for k in range(j+2, n):
                    if k == n-1 and i == 0: continue
                    subs.append((i, j, k))
        return subs

    n = 5
    while True:
        subs = stable_3subsets(n)
        if len(subs) >= N: break
        n += 1

    if len(subs) != N:
        # Try to trim or expand
        if len(subs) < N: return []
        subs = subs[:N]

    adj = [set() for _ in range(N)]
    # Two stable 3-subsets adjacent iff they are disjoint
    sub_sets = [set(s) for s in subs]
    for i in range(N):
        for j in range(i+1, N):
            if not sub_sets[i] & sub_sets[j]:  # disjoint
                adj[i].add(j); adj[j].add(i)

    # Add more K4-free edges (within same "column" by element-overlap)
    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    rng = random.Random(N * 97 + 23)
    non_edges = [(i, j) for i in range(N) for j in range(i+1, N) if j not in adj[i]]
    rng.shuffle(non_edges)
    cap = max(len(adj[v]) for v in range(N)) + 2
    for u, v in non_edges[:N*3]:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u, v) for u in range(N) for v in adj[u] if v > u]
