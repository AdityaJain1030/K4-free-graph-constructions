# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (IS-targeted edge swap: swap non-IS edges to IS edges)
# Hypothesis: swapping edges FROM outside IS TO inside IS reduces alpha without increasing d_max
# Why non-VT: IS-guided edge swaps create unique non-regular degree structure per graph

import random

def _exact_alpha_set(adj, N):
    best = [0, set()]
    def bb(cands, cur, cs):
        if cur + len(cands) <= best[0]: return
        if not cands:
            if cur > best[0]: best[0] = cur; best[1] = frozenset(cs)
            return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur, cs)
        bb(cands - {v} - adj[v], cur+1, cs | {v})
    bb(set(range(N)), 0, set())
    return best[0], best[1]

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
                            adj[u].discard(v); adj[v].discard(u)
                            changed = True; break
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

    # IS-targeted edge swaps: only at small N
    if N <= 40:
        for _ in range(60):
            alpha, IS = _exact_alpha_set(adj, N)
            if alpha <= 5: break
            IS = list(IS)
            # Find IS pair (u,v) - not adjacent
            swapped = False
            rng.shuffle(IS)
            for i in range(len(IS)):
                for j in range(i+1, len(IS)):
                    u, v = IS[i], IS[j]
                    if v in adj[u]: continue
                    # Try direct add
                    if not has_k4(u, v):
                        adj[u].add(v); adj[v].add(u)
                        swapped = True; break
                    # Try swap: remove edge (a,b) outside IS, add (u,v)
                    for a in range(N):
                        if a in set(IS): continue
                        for b in list(adj[a]):
                            if b <= a or b in set(IS): continue
                            adj[a].discard(b); adj[b].discard(a)
                            if not has_k4(u, v):
                                adj[u].add(v); adj[v].add(u)
                                swapped = True; break
                            adj[a].add(b); adj[b].add(a)
                        if swapped: break
                    if swapped: break
                if swapped: break
            if not swapped: break

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
