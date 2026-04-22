"""
scripts/run_rung3_lovasz_theta.py
=================================
Rung 3: the Lovasz theta SDP as a per-graph upper bound on alpha
(and therefore also a rigorous upper bound on the c-bound derivable
from any SDP-relaxation-of-alpha method).

Why this matters for our question:
  * Rung 0 and rung 2 are hard-core lower bounds on alpha(G).
  * Lovasz theta theta(G) is an SDP *upper* bound on alpha(G):
        alpha(G) <= theta(G).
  * A universal bound of the form "c(G) >= c* for all K4-free G"
    is EQUIVALENT, for vertex-transitive G, to
        alpha(G) / n >= c* / ln d_max.
  * theta(G) tells us the *best possible* lower bound an SDP
    relaxation of alpha can produce: if theta(G) / n < X, no SDP
    argument can prove alpha/n >= X for that graph.

For each K4-free DB graph we compute:
  (a) theta(G) by the Lovasz SDP
       minimise  t
       s.t.      Y is (n+1)x(n+1) PSD,
                 Y[0,0] = 1,
                 sum_{ij} Y[i+1,j+1] = t,
                 Y[i+1,i+1] = Y[0,i+1] for all i,
                 Y[i+1,j+1] = 0 for ij in E(G).
       (This is the formulation that gives theta(G) = alpha(G)
        for perfect graphs and theta(Paley_q) = sqrt(q).)
  (b) Ratschmidt / Schrijver's theta'(G)? Not needed here; theta
      alone is enough to show the SDP ceiling.

Output:
  * rung3_theta.csv  (graph_id, n, d_max, alpha, theta, theta/alpha,
                      theta_c_log = theta*d_max / (n*ln d_max))
  * rung3_theta.png  (theta vs alpha tightness; theta-derived c_log
                      alongside actual c_log)

Scope / honesty:
  * This is per-graph, not universal. A universal bound would
    require enumerating or flag-algebra-bounding theta over all
    K4-free graphs of given d_max.
  * cvxpy + SCS gives ~1e-5 accuracy; we round to 4 dp.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB

try:
    import cvxpy as cp
except ImportError as e:
    print("cvxpy is required:  pip install cvxpy", file=sys.stderr)
    raise


def lovasz_theta(G, solver="SCS", verbose=False):
    """
    Lovasz theta via the (n+1)x(n+1) formulation:
        maximise  sum_i,j J_ij * X_ij  =  <J, X>
        s.t.      X psd, X_ii = 1,
                 X_ij = 0 for ij not in E(G) and i != j.
    (This is the CLIQUE formulation: theta of the complement = theta of G.
     Equivalently, for independent sets: work on the complement graph.)

    Here: want alpha upper bound, which equals theta(complement of G).
    Equivalent formulation directly:
        maximise  sum_ij X_ij
        s.t.      X psd, trace(X) = 1,
                 X_ij = 0 for ij in E(G).
    That gives theta(G) where theta(G) >= alpha(G).
    """
    n = G.number_of_nodes()
    nodes = list(G.nodes())
    idx = {v: i for i, v in enumerate(nodes)}

    X = cp.Variable((n, n), symmetric=True)
    constraints = [X >> 0, cp.trace(X) == 1]
    for (u, v) in G.edges():
        i, j = idx[u], idx[v]
        constraints.append(X[i, j] == 0)

    obj = cp.Maximize(cp.sum(X))
    prob = cp.Problem(obj, constraints)
    prob.solve(solver=solver, verbose=verbose)
    return float(prob.value)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-max", type=int, default=20)
    ap.add_argument("--solver", default="SCS")
    ap.add_argument("--out-dir", default=os.path.join(REPO, "results", "subplan_b"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)

    print(f"[rung3] opening DB (n<={args.n_max}) ...", flush=True)
    with DB(auto_sync=False) as db:
        rows = db.raw_execute(
            "SELECT graph_id, n, d_max, alpha, c_log "
            "FROM cache WHERE is_k4_free=1 AND alpha IS NOT NULL "
            "AND c_log IS NOT NULL AND n <= ? ORDER BY n, c_log",
            (args.n_max,),
        )
        seen = set()
        unique = []
        for r in rows:
            if r["graph_id"] not in seen:
                seen.add(r["graph_id"])
                unique.append(r)
        print(f"[rung3] {len(unique)} unique K4-free graphs", flush=True)
        graphs = [(r, db.nx(r["graph_id"])) for r in unique]

    results = []
    t0 = time.time()
    for i, (r, G) in enumerate(graphs):
        try:
            theta = lovasz_theta(G, solver=args.solver)
        except Exception as e:
            print(f"  skip {r['graph_id'][:8]}: {e}")
            continue
        alpha = r["alpha"]
        d_max = r["d_max"]
        N = r["n"]
        c_theta = theta * d_max / (N * math.log(d_max)) if d_max >= 2 else None
        results.append(dict(
            graph_id=r["graph_id"], n=N, d_max=d_max,
            alpha=alpha, theta=theta,
            theta_over_alpha=theta / alpha if alpha else None,
            c_log=r["c_log"],
            c_theta=c_theta,
        ))
        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            print(f"  [{i+1}/{len(graphs)}] n={N} d_max={d_max} "
                  f"alpha={alpha} theta={theta:.3f}  "
                  f"(avg {elapsed/(i+1):.2f}s/graph)", flush=True)

    # CSV
    out_csv = os.path.join(args.out_dir, "rung3_theta.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
        w.writeheader()
        for row in results:
            w.writerow(row)
    print(f"[rung3] wrote {out_csv}", flush=True)

    # Quick summary
    ratios = [r["theta_over_alpha"] for r in results]
    print(f"[rung3] theta/alpha: min={min(ratios):.4f}, "
          f"mean={np.mean(ratios):.4f}, max={max(ratios):.4f}")

    # Paley-like graphs: theta = sqrt(n)
    paley_like = [r for r in results
                  if r["n"] == 17 and r["d_max"] == 8]
    if paley_like:
        p = paley_like[0]
        print(f"[rung3] Paley P17: n=17, alpha=3, theta={p['theta']:.4f} "
              f"(sqrt(17)={math.sqrt(17):.4f})")


if __name__ == "__main__":
    main()
