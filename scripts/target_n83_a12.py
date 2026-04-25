"""
Targeted SAT near-regular search: n=83, α=12, D ∈ [2..28].

Break-even for c_log improvement over current frontier (c=0.927 at n=83):
   12·d/(83·ln d) < 0.927  →  d/ln(d) < 6.414  →  d ≤ 28.

Iterates D = 2, 3, ..., 28 (each pinned), budgets 300s per D,
saves any K4-free graphs found to graph_db.
"""
import os, sys, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db import DB
from search import SATNearRegularNonReg
from utils.nauty import canonical_id

N = 83
ALPHA = 12
D_RANGE = list(range(2, 29))
PER_D_TIMEOUT = 300.0
TOTAL_TIMEOUT = 1800.0  # hard stop

t_start = time.monotonic()
db = DB(auto_sync=False)
found = []

for D in D_RANGE:
    elapsed = time.monotonic() - t_start
    if elapsed > TOTAL_TIMEOUT:
        print(f"\n[TIMEOUT] stopping after {elapsed:.0f}s")
        break
    c_bound = ALPHA * D / (N * math.log(D)) if D > 1 else float("inf")
    if c_bound >= 0.927:
        continue  # would not improve frontier
    print(f"\n=== D={D}  projected c={c_bound:.4f}  (best={0.927:.4f})  [{elapsed:.0f}s elapsed] ===", flush=True)
    try:
        search = SATNearRegularNonReg(
            n=N, alpha=ALPHA, D=D,
            scan_mode="first", max_iso_per_D=5, max_labeled_per_D=50,
            per_D_timeout_s=PER_D_TIMEOUT, timeout_s=PER_D_TIMEOUT+10,
            symmetry_mode="chain", workers=16, verbosity=1,
        )
        graphs = search.run()
    except Exception as e:
        print(f"  [ERROR] D={D}: {e}")
        continue
    print(f"  D={D}: {len(graphs)} graphs found")
    for G in graphs:
        gid, was_new = db.add(G, source="sat_near_regular_nonreg",
                              filename="sat_near_regular_nonreg.json",
                              n=N, D=D, alpha_cap=ALPHA,
                              iso_canonical_id=canonical_id(G)[0])
        print(f"    [{('ADDED' if was_new else 'DUP')}] id={gid[:10]}  d_max={max(dict(G.degree()).values())}")
        found.append((D, gid, was_new))

print(f"\n=== Summary: {len(found)} graphs touched in {time.monotonic()-t_start:.0f}s ===")
for D, gid, was_new in found:
    print(f"  D={D}  id={gid[:10]}  {'new' if was_new else 'dup'}")
