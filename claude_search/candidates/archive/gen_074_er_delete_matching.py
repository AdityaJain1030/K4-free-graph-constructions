# Family: polarity
# Catalog: er_polarity_delete_matching
# Parent: gen_056_er_local_improve (build ER(q) then delete matching on non-absolute orbit)
# Hypothesis: deleting q^2/2 matched edges from non-absolute orbit drops d_max by 1 at negligible α cost
# Why non-VT: matched vertices have degree q; unmatched non-absolute have q+1; three degree classes

import random

def construct(N):
    q = None
    for p in [7, 11, 13]:
        if p*p + p + 1 == N: q = p; break
    if q is None: return []

    def canonical(x, y, z):
        for v in [x, y, z]:
            if v % q != 0:
                inv = pow(v, q-2, q)
                return (x*inv % q, y*inv % q, z*inv % q)
        return None

    pts = {}; pts_list = []
    for x in range(q):
        for y in range(q):
            for z in range(q):
                if x == 0 and y == 0 and z == 0: continue
                can = canonical(x, y, z)
                if can not in pts:
                    pts[can] = len(pts_list); pts_list.append(can)

    adj = [set() for _ in range(N)]
    for i in range(N):
        for j in range(i+1, N):
            p, pp = pts_list[i], pts_list[j]
            dot = (p[0]*pp[0] + p[1]*pp[1] + p[2]*pp[2]) % q
            if dot == 0:
                adj[i].add(j); adj[j].add(i)

    # Non-absolute points: p.p != 0
    non_abs = [i for i in range(N)
               if (pts_list[i][0]**2 + pts_list[i][1]**2 + pts_list[i][2]**2) % q != 0]

    # Delete a deterministic matching: pair non-abs[i] with non_abs[i + q^2 // 2] if edge exists
    rng = random.Random(N * 41 + 7)
    shuffled = non_abs[:]
    rng.shuffle(shuffled)
    for idx in range(0, len(shuffled)-1, 2):
        u, v = shuffled[idx], shuffled[idx+1]
        if v in adj[u]:
            adj[u].discard(v); adj[v].discard(u)

    return [(u, v) for u in range(N) for v in adj[u] if v > u]
