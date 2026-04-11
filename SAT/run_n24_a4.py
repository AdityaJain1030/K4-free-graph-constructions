"""Find minimum d_max for K₄-free graph on N=24, α≤4.

Usage:
    micromamba run -n ILP_pareto_enum python run_n24_a4.py
"""
from regular_sat.solver import _solve_for_D_direct
from k4free_ilp.graph_io import adj_to_g6
from k4free_ilp.alpha_exact import alpha_exact
import os
import numpy as np

n, alpha, w = 24, 4, 8
print(f"Workers: {w}")

for D in [7, 8, 9]:
    print(f"=== D={D} ===", flush=True)
    status, adj = _solve_for_D_direct(n, alpha, D, 1800, w)
    if adj is not None:
        ne = int(np.sum(adj)) // 2
        degs = sorted(set(adj.sum(axis=1).astype(int).tolist()))
        a, _ = alpha_exact(adj)
        g6 = adj_to_g6(adj)
        print(f"  FEASIBLE, edges={ne}, degrees={degs}")
        print(f"  alpha={a}, g6={g6}")
        break
    else:
        print(f"  {status}")
