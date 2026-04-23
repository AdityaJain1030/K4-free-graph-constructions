"""
Compute Lovász θ for every unique K4-free graph in the DB that has
α known, across ALL sources. One row per graph_id (prefer the best-
c_log source if a graph appears under multiple sources).
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys
import time

import cvxpy as cp
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
from graph_db import DB  # noqa: E402


def lovasz_theta_adj(A: np.ndarray, solver: str = "SCS") -> float:
    n = A.shape[0]
    X = cp.Variable((n, n), symmetric=True)
    cons = [X >> 0, cp.trace(X) == 1]
    iu, ju = np.where(np.triu(A, 1) > 0)
    for i, j in zip(iu, ju):
        cons.append(X[i, j] == 0)
    prob = cp.Problem(cp.Maximize(cp.sum(X)), cons)
    prob.solve(solver=solver, verbose=False)
    return float(prob.value)


def main():
    out_csv = os.path.join(REPO, "results", "all_k4free_theta.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    with DB(auto_sync=False) as db:
        # best (lowest) c_log per graph_id, with source + properties
        rows = db.raw_execute("""
            SELECT c.graph_id, c.source, c.n, c.d_max, c.d_avg, c.alpha,
                   c.c_log, c.eigenvalues_adj, c.is_regular,
                   c.regularity_d, c.metadata
            FROM cache c
            INNER JOIN (
                SELECT graph_id, MIN(c_log) AS best_c
                FROM cache
                WHERE is_k4_free=1 AND alpha IS NOT NULL AND c_log IS NOT NULL
                GROUP BY graph_id
            ) b ON b.graph_id = c.graph_id AND b.best_c = c.c_log
            WHERE c.is_k4_free=1 AND c.alpha IS NOT NULL
            ORDER BY c.n, c.c_log
        """)
        seen = set()
        uniq = []
        for r in rows:
            if r["graph_id"] in seen: continue
            seen.add(r["graph_id"])
            uniq.append(r)
        print(f"[theta-all] {len(uniq)} unique K4-free graphs", flush=True)
        import networkx as nx
        graphs = [(r, db.nx(r["graph_id"])) for r in uniq]

    results = []
    t0 = time.time()
    for i, (r, G) in enumerate(graphs):
        n = r["n"]
        alpha = r["alpha"]
        ev = r["eigenvalues_adj"]
        if isinstance(ev, str):
            ev = json.loads(ev)
        lam_min = float(sorted(ev)[0])
        d = r["regularity_d"] if r["is_regular"] else r["d_avg"]
        hoff = n * (-lam_min) / (d - lam_min) if d != lam_min else float("inf")

        A = np.asarray(__import__("networkx").to_numpy_array(G, dtype=float))
        try:
            theta = lovasz_theta_adj(A)
        except Exception as e:
            print(f"  skip {r['graph_id'][:10]} n={n} src={r['source']}: {e}",
                  flush=True)
            continue

        results.append(dict(
            graph_id=r["graph_id"], source=r["source"], n=n, d=d,
            alpha=int(alpha), lam_min=lam_min,
            hoffman=hoff, theta=theta,
            theta_over_alpha=theta/alpha if alpha else None,
            alpha_over_theta=alpha/theta if theta else None,
            theta_over_hoff=theta/hoff if hoff and hoff < float("inf") else None,
            alpha_over_hoff=alpha/hoff if hoff and hoff < float("inf") else None,
            c_log=r["c_log"],
        ))

        if (i + 1) % 25 == 0 or i + 1 == len(graphs):
            dt = time.time() - t0
            print(f"  [{i+1}/{len(graphs)}] n={n} src={r['source']:20s} "
                  f"α={alpha} θ={theta:.3f} H={hoff:.3f} "
                  f"({dt/(i+1):.2f}s/graph, elapsed {dt:.0f}s)",
                  flush=True)

    fields = list(results[0].keys())
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow(row)
    print(f"[theta-all] wrote {out_csv}", flush=True)


if __name__ == "__main__":
    main()
