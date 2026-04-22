# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (inject edges within max IS to shrink α directly)
# Hypothesis: adding K4-free edges within IS forces α reduction; 3 injections may reach α=5
# Why non-VT: IS-guided edge injection produces highly non-uniform degree sequence

import random

def _bb_alpha(adj, N):
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands:
            if cur > best[0]: best[0] = cur
            return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur)
        bb(cands - {v} - adj[v], cur + 1)
    bb(set(range(N)), 0)
    return best[0]

def _max_is(adj, N):
    best = [[]]
    def bb(cands, cur):
        if cur + len(cands) <= len(best[0]):
            if cur > len(best[0]): best[0] = list(cur_set[:cur])
            return
        if not cands:
            if cur > len(best[0]): best[0] = list(cur_set[:cur])
            return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        cands.discard(v)
        bb(set(cands), cur)
        # This simplified version doesn't track actual set; use greedy instead
    # Greedy IS
    deg = [len(adj[i]) for i in range(N)]
    order = sorted(range(N), key=lambda x: deg[x])
    IS = []; blocked = set()
    for v in order:
        if v not in blocked:
            IS.append(v); blocked |= adj[v]
    return IS

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
                common = list(adj[u] & adj[v])
                for a in range(len(common)):
                    for b in range(a+1, len(common)):
                        if common[b] in adj[common[a]]:
                            adj[u].discard(v); adj[v].discard(u)
                            changed = True; break
                    if changed: break
                if changed: break
            if changed: break

    def has_k4(u, v):
        common = list(adj[u] & adj[v])
        for a in range(len(common)):
            for b in range(a+1, len(common)):
                if common[b] in adj[common[a]]: return True
        return False

    cands = [(i,j) for i in range(N) for j in range(i+1,N) if j not in adj[i]]
    rng.shuffle(cands)
    cap = target_d + 1
    for u, v in cands:
        if len(adj[u]) <= cap and len(adj[v]) <= cap and not has_k4(u, v):
            adj[u].add(v); adj[v].add(u)

    # IS injection: add edges within IS to break large independent sets
    max_rounds = 20
    for _ in range(max_rounds):
        IS = _max_is(adj, N)
        injected = False
        for i in range(len(IS)):
            for j in range(i+1, len(IS)):
                u, v = IS[i], IS[j]
                if v not in adj[u] and not has_k4(u, v):
                    adj[u].add(v); adj[v].add(u)
                    injected = True; break
            if injected: break
        if not injected: break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
