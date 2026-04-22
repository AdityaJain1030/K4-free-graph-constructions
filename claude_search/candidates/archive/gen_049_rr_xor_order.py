# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (XOR-based deterministic stub ordering instead of random shuffle)
# Hypothesis: XOR-ordered stubs give different graph structure with potentially smaller α
# Why non-VT: XOR pairing creates non-cyclic adjacency structure, breaking symmetry

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1

    # Build stubs: vertex v repeated target_d times, but ordered by v XOR stub_index
    stubs = []
    for v in range(N):
        for k in range(target_d):
            stubs.append(v ^ (k * 7 % N))  # XOR-perturbed identity
    # Sort stubs by value (not random shuffle)
    stubs.sort(key=lambda x: (x, stubs.index(x)))

    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs)-1, 2):
        u, v = stubs[i] % N, stubs[i+1] % N
        if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    changed = True
    while changed:
        changed = False
        for u in range(N):
            for v in list(adj[u]):
                if v <= u: continue
                common = list(adj[u] & adj[v])
                for a in range(len(common)):
                    for b in range(a+1, len(common)):
                        if common[b] in adj[common[a]]:
                            adj[u].discard(v); adj[v].discard(u); changed = True; break
                    if changed: break
                if changed: break
            if changed: break

    import random
    rng = random.Random(N * 103 + 71)
    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
