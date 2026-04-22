# Family: asymmetric_lift
# Catalog: asymmetric_lift_generic
# Parent: gen_022_asymmetric_lift_er7 (voltage lift of Petersen graph; girth 5 guaranteed K4-free)
# Hypothesis: Petersen lift with optimized voltages gives K4-free expander with α < 0.19N
# Why non-VT: random voltages destroy the Petersen Aut group; lift has trivial Aut typically

import random

def construct(N):
    # Petersen graph structure
    petersen_adj = [set() for _ in range(10)]
    # Outer 5-cycle: 0-1-2-3-4-0
    for i in range(5): petersen_adj[i].add((i+1)%5); petersen_adj[(i+1)%5].add(i)
    # Inner pentagram: 5-7-9-6-8-5
    inner = [5, 7, 9, 6, 8]
    for i in range(5): petersen_adj[inner[i]].add(inner[(i+2)%5]); petersen_adj[inner[(i+2)%5]].add(inner[i])
    # Spokes: i ~ i+5
    for i in range(5): petersen_adj[i].add(i+5); petersen_adj[i+5].add(i)

    t = N // 10
    if t < 4 or t * 10 != N: return []  # Only valid at multiples of 10

    rng = random.Random(N * 151 + 73)
    # Voltage from Z_t on each directed edge
    voltage = {}
    for u in range(10):
        for v in petersen_adj[u]:
            if v > u:
                vol = rng.randint(0, t-1)
                voltage[(u,v)] = vol
                voltage[(v,u)] = (-vol) % t

    # Lift: vertex (v, k) for v in 0..9, k in 0..t-1
    def idx(v, k): return v*t + k
    adj = [set() for _ in range(N)]
    for u in range(10):
        for v in petersen_adj[u]:
            vol = voltage[(u,v)]
            for k in range(t):
                uk = idx(u, k); vk = idx(v, (k+vol)%t)
                adj[uk].add(vk); adj[vk].add(uk)

    # The lift has girth ≥ 5 iff voltages are "cycle-free" (mod t)
    # Check and remove any K4 edges (in case girth = 3 or 4 sneak in)
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

    return [(u,v) for u in range(N) for v in adj[u] if v > u]
