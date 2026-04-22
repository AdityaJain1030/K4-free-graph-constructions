# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (allow d_max=8 to add IS-internal edges; α=7 target)
# Hypothesis: adding one IS-internal K4-free edge to 7-regular graph reduces α to 7 at N=30
# Why non-VT: IS-internal edge addition creates unique degree-8 vertex breaking vertex-transitivity

import random

def _exact_alpha(adj, N):
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands: best[0] = max(best[0], cur); return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur); bb(cands - {v} - adj[v], cur+1)
    bb(set(range(N)), 0)
    return best[0]

def construct(N):
    target_d = int(N**0.5) + 1
    if target_d * N % 2 != 0: target_d += 1
    rng = random.Random(N * 101 + 61)

    stubs = []
    for v in range(N): stubs.extend([v] * target_d)
    rng.shuffle(stubs)
    adj = [set() for _ in range(N)]
    for i in range(0, len(stubs)-1, 2):
        u, v = stubs[i], stubs[i+1]
        if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)

    changed = True
    while changed:
        changed = False
        for u in range(N):
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

    def has_k4(u, v):
        cm = list(adj[u] & adj[v])
        for a in range(len(cm)):
            for b in range(a+1, len(cm)):
                if cm[b] in adj[cm[a]]: return True
        return False

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    # Try IS-internal edges with relaxed d_max constraint
    if N <= 45:
        cur_a = _exact_alpha(adj, N)
        for _ in range(50):
            if cur_a <= 5: break
            # Find greedy IS
            deg = [len(adj[i]) for i in range(N)]
            order = sorted(range(N), key=lambda x: deg[x])
            IS = set(); blocked = set()
            for v in order:
                if v not in blocked: IS.add(v); blocked |= adj[v]
            IS_list = list(IS)
            added = False
            for i in range(len(IS_list)):
                for j in range(i+1, len(IS_list)):
                    u, v = IS_list[i], IS_list[j]
                    if v not in adj[u] and not has_k4(u, v):
                        adj[u].add(v); adj[v].add(u)
                        new_a = _exact_alpha(adj, N)
                        if new_a < cur_a:
                            cur_a = new_a; added = True; break
                        else:
                            adj[u].discard(v); adj[v].discard(u)
                if added: break
            if not added: break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
