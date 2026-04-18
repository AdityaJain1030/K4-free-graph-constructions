# Family: hash
"""K4-free graph via hash-based edge selection maintaining regularity."""

import hashlib

def construct(N):
    edges = []
    target_deg = 6 if N >= 10 else 4

    for i in range(N):
        targets = set()
        for j in range(N):
            if i != j:
                h = hashlib.md5(f"{i},{j}".encode()).digest()
                val = int.from_bytes(h, 'big') % (N - 1)
                if val < target_deg and j not in targets:
                    targets.add(j)
                    if len(targets) == target_deg:
                        break

        for j in targets:
            if i < j:
                edges.append((i, j))

    return list(set(edges))
