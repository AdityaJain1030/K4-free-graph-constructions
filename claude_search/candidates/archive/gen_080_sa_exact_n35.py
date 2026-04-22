# Family: core_periphery
# Catalog: bohman_keevash_k4_process
# Parent: gen_037_random_regular_k4free (SA on edge swaps with exact IS; targeting α=7 at N=35)
# Hypothesis: 200 SA steps with exact IS from 5 multi-starts can reach α=7 in K4-free 6-regular N=35
# Why non-VT: random initial construction + SA perturbations destroys all symmetry

import random, math

def _exact_alpha(adj, N):
    best = [0]
    def bb(cands, cur):
        if cur + len(cands) <= best[0]: return
        if not cands: best[0] = max(best[0], cur); return
        v = max(cands, key=lambda x: len(adj[x] & cands))
        bb(cands - {v}, cur); bb(cands - {v} - adj[v], cur+1)
    bb(set(range(N)), 0)
    return best[0]

def _has_k4(adj, u, v):
    cm = list(adj[u] & adj[v])
    for a in range(len(cm)):
        for b in range(a+1, len(cm)):
            if cm[b] in adj[cm[a]]: return True
    return False

def construct(N):
    if N != 35: return []
    target_d = 6
    rng = random.Random(N * 12345 + 1)
    best_adj = None; best_a = N

    for start in range(5):
        stubs = []
        for v in range(N): stubs.extend([v] * target_d)
        rng.shuffle(stubs)
        adj = [set() for _ in range(N)]
        for i in range(0, len(stubs)-1, 2):
            u, v = stubs[i], stubs[i+1]
            if u != v and v not in adj[u]: adj[u].add(v); adj[v].add(u)
        # K4 removal
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

        cur_a = _exact_alpha(adj, N)
        T = 2.0
        for step in range(200):
            edges = [(u,v) for u in range(N) for v in adj[u] if v > u]
            non_edges = [(u,v) for u in range(N) for v in range(u+1,N) if v not in adj[u]]
            if not edges or not non_edges: break
            e1 = rng.choice(edges); e2 = rng.choice(non_edges)
            u1,v1 = e1; u2,v2 = e2
            adj[u1].discard(v1); adj[v1].discard(u1)
            if not _has_k4(adj, u2, v2):
                adj[u2].add(v2); adj[v2].add(u2)
                new_a = _exact_alpha(adj, N)
                delta = new_a - cur_a
                if delta < 0 or rng.random() < math.exp(-delta/T):
                    cur_a = new_a
                else:
                    adj[u2].discard(v2); adj[v2].discard(u2)
                    adj[u1].add(v1); adj[v1].add(u1)
            else:
                adj[u1].add(v1); adj[v1].add(u1)
            T *= 0.97

        if cur_a < best_a: best_a = cur_a; best_adj = [s.copy() for s in adj]

    return [(u,v) for u in range(N) for v in best_adj[u] if v > u]
