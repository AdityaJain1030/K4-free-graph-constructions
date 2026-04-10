#!/usr/bin/env python3
"""SAT encoding: K₄-free graph, N=24, α≤4, degrees in {8,9}.

Pure CNF via PySAT with CaDiCaL backend. Also writes DIMACS file
so you can run any external solver (kissat, cadical, etc.).

Usage:
    micromamba run -n ILP_pareto_enum pip install python-sat  # if needed
    micromamba run -n ILP_pareto_enum python sat_n24_d8.py
    micromamba run -n ILP_pareto_enum python sat_n24_d8.py --dimacs-only
"""

import sys
import time
import threading
from itertools import combinations
from math import comb

# ── Configuration ─────────────────────────────────────────────
N = 24
ALPHA = 4
D = 8          # degrees in {D, D+1} = {8, 9}
TIMEOUT = 3600

# ── Edge variables (1-indexed for SAT) ────────────────────────
edge_id = {}
vid = 0
for i in range(N):
    for j in range(i + 1, N):
        vid += 1
        edge_id[(i, j)] = vid

NUM_EDGE = vid  # C(24,2) = 276


def ev(i, j):
    return edge_id[(min(i, j), max(i, j))]


# ── Build CNF ─────────────────────────────────────────────────
from pysat.card import CardEnc, EncType

clauses = []
top = NUM_EDGE

# 1) K₄-free: no 4-clique ⟹ for each 4-set, at least one edge absent
n_k4 = comb(N, 4)
print(f"K4-free: {n_k4} clauses (one per 4-subset)")
for a, b, c, d in combinations(range(N), 4):
    clauses.append([
        -ev(a, b), -ev(a, c), -ev(a, d),
        -ev(b, c), -ev(b, d), -ev(c, d),
    ])

# 2) α ≤ 4: every 5-set has ≥1 edge
n_alpha = comb(N, ALPHA + 1)
print(f"Alpha ≤ {ALPHA}: {n_alpha} clauses (one per 5-subset)")
for S in combinations(range(N), ALPHA + 1):
    clauses.append([ev(S[a], S[b]) for a in range(5) for b in range(a + 1, 5)])

# 3) Degree constraints: D ≤ deg(v) ≤ D+1 via totalizer encoding
print(f"Degree ∈ {{{D},{D+1}}}: 2×{N} cardinality constraints")
for v in range(N):
    lits = [ev(v, j) for j in range(N) if j != v]

    cnf = CardEnc.atleast(lits, bound=D, top_id=top, encoding=EncType.totalizer)
    if cnf.clauses:
        top = cnf.nv
        clauses.extend(cnf.clauses)

    cnf = CardEnc.atmost(lits, bound=D + 1, top_id=top, encoding=EncType.totalizer)
    if cnf.clauses:
        top = cnf.nv
        clauses.extend(cnf.clauses)

# 4) Symmetry break: WLOG vertex 0 is adjacent to vertex 1
#    (valid since min degree ≥ 8, so every vertex has neighbors)
clauses.append([ev(0, 1)])

print(f"\nTotal: {top} variables, {len(clauses)} clauses")

# ── Write DIMACS ──────────────────────────────────────────────
dimacs_file = f"n{N}_d{D}.cnf"
print(f"Writing {dimacs_file} ...")
with open(dimacs_file, "w") as f:
    f.write(f"c K4-free N={N} alpha<={ALPHA} deg in {{{D},{D+1}}}\n")
    f.write(f"c edge vars 1..{NUM_EDGE}  aux {NUM_EDGE+1}..{top}\n")
    f.write(f"p cnf {top} {len(clauses)}\n")
    for cl in clauses:
        f.write(" ".join(map(str, cl)) + " 0\n")
print(f"  {dimacs_file}: {top} vars, {len(clauses)} clauses")

if "--dimacs-only" in sys.argv:
    print("\nDIMACS written. Run externally:")
    print(f"  kissat {dimacs_file}        # or")
    print(f"  cadical {dimacs_file}")
    sys.exit(0)

# ── Solve ─────────────────────────────────────────────────────
try:
    from pysat.solvers import Cadical153 as SolverCls
    solver_name = "CaDiCaL 1.5.3"
except ImportError:
    from pysat.solvers import Glucose4 as SolverCls
    solver_name = "Glucose4"

print(f"\nSolving with {solver_name}  (timeout {TIMEOUT}s) ...", flush=True)

solver = SolverCls()
for cl in clauses:
    solver.add_clause(cl)


def on_timeout():
    solver.interrupt()


timer = threading.Timer(TIMEOUT, on_timeout)
t0 = time.time()
timer.start()
result = solver.solve_limited(expect=0)
timer.cancel()
elapsed = time.time() - t0

# ── Report ────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"Elapsed: {elapsed:.1f}s")

if result is True:
    model = set(solver.get_model())
    print(f"RESULT: SAT — D={D} is FEASIBLE\n")

    import numpy as np
    adj = np.zeros((N, N), dtype=int)
    for (i, j), var in edge_id.items():
        if var in model:
            adj[i][j] = adj[j][i] = 1

    ne = adj.sum() // 2
    degs = sorted(set(adj.sum(axis=1).tolist()))
    print(f"  Edges: {ne}")
    print(f"  Degrees: {degs}")

    try:
        sys.path.insert(0, ".")
        from k4free_ilp.alpha_exact import alpha_exact
        from k4free_ilp.k4_check import is_k4_free
        from k4free_ilp.graph_io import adj_to_g6

        print(f"  K4-free: {is_k4_free(adj)}")
        a, _ = alpha_exact(adj)
        print(f"  Alpha: {a}")
        print(f"  g6: {adj_to_g6(adj)}")
    except ImportError:
        print("  (k4free_ilp not on path — skipping validation)")

elif result is False:
    print(f"RESULT: UNSAT — D={D} is INFEASIBLE for N={N}, α≤{ALPHA}")

else:
    print(f"RESULT: UNKNOWN (timeout or interrupted after {elapsed:.1f}s)")

solver.delete()
