# Family: invented
# Catalog: bohman_keevash_k4_process
# Parent: gen_077_5partite_k4free (Cartesian product G□H; ω=max(ω(G),ω(H))≤3 if both K4-free)
# Hypothesis: Cartesian product of two K4-free graphs is K4-free; careful choice gives α improvement
# Why non-VT: product of non-VT graphs is non-VT; asymmetric random base factors

import random

def construct(N):
    # Find factorization N = n1 * n2 with n1, n2 ≥ 5
    n1, n2 = None, None
    for a in range(5, N//5 + 1):
        if N % a == 0 and N // a >= 5:
            n1, n2 = a, N // a; break
    if n1 is None: return []

    rng = random.Random(N * 220381 + 11)

    def build_k4free(n, seed, td):
        r = random.Random(seed)
        stubs = [v for v in range(n) for _ in range(td)]
        r.shuffle(stubs)
        adj = [set() for _ in range(n)]
        for i in range(0, len(stubs)-1, 2):
            u, v = stubs[i], stubs[i+1]
            if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)
        changed = True
        while changed:
            changed = False
            for u in range(n):
                for v in list(adj[u]):
                    if v <= u: continue
                    cm = list(adj[u] & adj[v])
                    for a in range(len(cm)):
                        for b in range(a+1, len(cm)):
                            if cm[b] in adj[cm[a]]:
                                adj[u].discard(v); adj[v].discard(u); changed=True; break
                        if changed: break
                    if changed: break
            if changed: break
        return adj

    td1 = max(2, int(n1**0.5)); td2 = max(2, int(n2**0.5))
    g1 = build_k4free(n1, N*3 + 1, td1)
    g2 = build_k4free(n2, N*7 + 5, td2)

    # Cartesian product: (a,b) ~ (c,d) iff (a=c and b~d in g2) or (a~c in g1 and b=d)
    def idx(a, b): return a * n2 + b
    adj = [set() for _ in range(N)]
    for a in range(n1):
        for b in range(n2):
            for b2 in g2[b]:
                if b2 > b:
                    adj[idx(a,b)].add(idx(a,b2)); adj[idx(a,b2)].add(idx(a,b))
            for a2 in g1[a]:
                if a2 > a:
                    adj[idx(a,b)].add(idx(a2,b)); adj[idx(a2,b)].add(idx(a,b))

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
