"""
Compute Lovász theta for every cayley_tabu_gap record and compare
against the Hoffman ratio bound  H(G) = n · (-λ_min) / (d − λ_min).

For vertex-transitive graphs  α ≤ θ ≤ H. Cayley graphs are vertex-
transitive, so theta being strictly below H would indicate SDP slack
beyond what the spectrum alone reveals.
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
    """
    θ(G) via  maximise ⟨J, X⟩  s.t.  X ⪰ 0, trace(X)=1, X_ij=0 for ij ∈ E(G).
    Returns an upper bound on α(G).
    """
    n = A.shape[0]
    X = cp.Variable((n, n), symmetric=True)
    cons = [X >> 0, cp.trace(X) == 1]
    iu, ju = np.where(np.triu(A, 1) > 0)
    for i, j in zip(iu, ju):
        cons.append(X[i, j] == 0)
    prob = cp.Problem(cp.Maximize(cp.sum(X)), cons)
    prob.solve(solver=solver, verbose=False)
    return float(prob.value)


def hoffman_bound(n: int, d: float, lam_min: float) -> float:
    return n * (-lam_min) / (d - lam_min)


def main():
    out_csv = os.path.join(REPO, "results", "cayley_gap_theta.csv")
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)

    with DB(auto_sync=False) as db:
        rows = db.raw_execute(
            "SELECT graph_id, n, d_max, d_avg, alpha, c_log, "
            "eigenvalues_adj, is_regular, regularity_d, metadata "
            "FROM cache WHERE source='cayley_tabu_gap' ORDER BY n, alpha DESC"
        )
        print(f"[theta] {len(rows)} cayley_tabu_gap records", flush=True)
        graphs = [(r, db.nx(r["graph_id"])) for r in rows]

    results = []
    t0 = time.time()
    for i, (r, G) in enumerate(graphs):
        n = r["n"]
        alpha = r["alpha"]
        ev = r["eigenvalues_adj"]
        if isinstance(ev, str):
            ev = json.loads(ev)
        eig = sorted(ev)
        lam_min = eig[0]
        d = r["regularity_d"] if r["is_regular"] else r["d_avg"]
        hoff = hoffman_bound(n, d, lam_min)

        A = np.asarray(__import__("networkx").to_numpy_array(G, dtype=float))
        try:
            theta = lovasz_theta_adj(A)
        except Exception as e:
            print(f"  skip {r['graph_id'][:10]} n={n}: {e}", flush=True)
            continue

        mt = r["metadata"] or "{}"
        if isinstance(mt, str):
            mt = json.loads(mt)
        group = mt.get("group") or mt.get("group_name") or mt.get("spec") or ""

        alpha_over_hoff = alpha / hoff if hoff > 0 else None
        theta_over_hoff = theta / hoff if hoff > 0 else None
        theta_over_alpha = theta / alpha if alpha else None
        theta_minus_alpha = theta - alpha

        results.append(dict(
            graph_id=r["graph_id"], n=n, d=d, alpha=alpha,
            lam_min=lam_min, hoffman=hoff, theta=theta,
            theta_over_alpha=theta_over_alpha,
            theta_over_hoff=theta_over_hoff,
            alpha_over_hoff=alpha_over_hoff,
            theta_minus_alpha=theta_minus_alpha,
            c_log=r["c_log"], group=group,
        ))

        if (i + 1) % 10 == 0 or i + 1 == len(graphs):
            dt = time.time() - t0
            print(f"  [{i+1}/{len(graphs)}] n={n} α={alpha} "
                  f"θ={theta:.3f} H={hoff:.3f} "
                  f"({dt/(i+1):.2f}s/graph)", flush=True)

    fields = list(results[0].keys())
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in results:
            w.writerow(row)
    print(f"[theta] wrote {out_csv}", flush=True)


if __name__ == "__main__":
    main()
