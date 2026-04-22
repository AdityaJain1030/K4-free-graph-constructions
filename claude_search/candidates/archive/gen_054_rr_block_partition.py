# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (block-partition vertices then build RR within+across blocks)
# Hypothesis: structured block partition with inter-block K4-free edges produces smaller IS
# Why non-VT: asymmetric block sizes and inter-block edge counts break vertex transitivity

import random

def construct(N):
    rng = random.Random(N * 137 + 53)
    k = max(3, int(N**0.5) // 2)  # block size ~sqrt(N)/2
    num_blocks = N // k
    remainder = N % k
    blocks = []
    v = 0
    for i in range(num_blocks):
        sz = k + (1 if i < remainder else 0)
        blocks.append(list(range(v, v+sz))); v += sz
    if v < N: blocks.append(list(range(v, N)))

    adj = [set() for _ in range(N)]

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    # Within each block: complete K4-free bipartite
    for blk in blocks:
        half = len(blk) // 2
        A = blk[:half]; B = blk[half:]
        for u in A:
            for v in B:
                if not has_k4(u, v):
                    adj[u].add(v); adj[v].add(u)

    # Across blocks: random K4-free edges with degree cap
    cap = int(N**0.5) + 2
    cross = [(u,v) for i,bi in enumerate(blocks) for j,bj in enumerate(blocks) if j>i
             for u in bi for v in bj]
    rng.shuffle(cross)
    for u, v in cross:
        if len(adj[u]) < cap and len(adj[v]) < cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
