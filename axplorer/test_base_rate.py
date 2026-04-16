"""
Quick base-rate test: how many random K_t-free graphs on N vertices
(built by _add_edges_greedily) also satisfy alpha(H) <= 3?

Run: python test_base_rate.py
"""
import numpy as np
from src.envs.kfour import _build_nbr_masks, _has_clique

N, t = 22, 5
N_TRIALS = 1000

def add_edges_greedily(N, t):
    data = np.zeros((N, N), dtype=np.uint8)
    nbr = [0] * N
    candidates = [(i, j) for i in range(N) for j in range(i + 1, N)]
    np.random.shuffle(candidates)
    for i, j in candidates:
        if _has_clique(t - 2, nbr[i] & nbr[j], nbr):
            continue
        data[i, j] = data[j, i] = 1
        nbr[i] |= 1 << j
        nbr[j] |= 1 << i
    return data, nbr

valid = 0
edges_valid, edges_all = [], []
for _ in range(N_TRIALS):
    data, nbr = add_edges_greedily(N, t)
    all_mask = (1 << N) - 1
    comp_nbr = [(all_mask ^ nbr[v]) & ~(1 << v) for v in range(N)]
    n_edges = int(data.sum()) // 2
    edges_all.append(n_edges)
    if not _has_clique(4, all_mask, comp_nbr):
        valid += 1
        edges_valid.append(n_edges)

print(f"N={N}, t={t}, trials={N_TRIALS}")
print(f"  Valid (alpha<=3): {valid}/{N_TRIALS}  ({100*valid/N_TRIALS:.1f}%)")
print(f"  Avg edges (all):   {np.mean(edges_all):.1f}")
if edges_valid:
    print(f"  Avg edges (valid): {np.mean(edges_valid):.1f}")
else:
    print(f"  Avg edges (valid): n/a")
