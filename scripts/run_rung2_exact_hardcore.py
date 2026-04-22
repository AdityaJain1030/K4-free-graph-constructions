"""
scripts/run_rung2_exact_hardcore.py
===================================
Rung 2: the *exact* hard-core occupancy bound.

Where rung 0 (subplan_b) used a local partition inequality
    rho_v(G, lambda) >= lambda / (lambda + Z(T_v, lambda))
which depends only on T_v, rung 2 computes the exact marginal
    rho_v(G, lambda) = lambda * Z(G - N[v], lambda) / Z(G, lambda)
for each vertex, aggregates, and takes the max over lambda.

This is the TIGHTEST bound attainable from the hard-core measure at
any fixed lambda. The gap between it and the true alpha(G) is
exactly the "information loss" of the hard-core measure (since
E_mu[|I|] -> alpha only as lambda -> infinity, where the polynomial
evaluation becomes numerically unstable).

By comparing rung 2 <-> actual alpha across the DB, we see the
fundamental ceiling of *any* hard-core-based local method, tree
recursion or flag algebra included.

What this script does:
  1. For each K4-free graph in graph_db with N <= n_max, compute
     Z(G, lambda) and Z(G - N[v], lambda) as integer polynomials.
  2. At each lambda on a grid, compute
         E_mu[|I|](lambda) = sum_v rho_v(G, lambda).
  3. Max over lambda => exact hard-core bound E_max(G).
  4. Also compute the infinite-lambda limit, which equals alpha(G)
     (sanity check), and the Davies-Jenssen-style TREE bound
         rho_tree(d, lambda) with lambda*y^{d+1} + y = 1.
  5. Aggregate per d_max: min E_max / N across DB graphs.
  6. Write CSV + plot comparing rung 0, rung 2, actual.

Honest scope:
  * The per-graph rung-2 bound is rigorous *for that graph*.
  * To get a UNIVERSAL bound on c(G) for all K4-free G with d_max=d,
    we need to show min E_max(G)/N over all such G equals some
    function of d. This script provides only the *empirical*
    minimum over the DB, which is an *upper* estimate of the
    universal bound - i.e. the true universal floor could be lower.
  * Still useful: if even the best-in-DB graphs have tight rung-2
    bounds that match alpha, the method has proved its ceiling.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict
from typing import List

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB


# ---------------------------------------------------------------------------
# Independence polynomial (re-used from subplan_b)
# ---------------------------------------------------------------------------

def independence_polynomial(H: nx.Graph) -> List[int]:
    """Z(H, lambda) = sum_k a_k lambda^k with a_k = #ind sets of size k."""
    nodes = list(H.nodes())
    if not nodes:
        return [1]
    nodes.sort(key=lambda v: -H.degree(v))
    index = {v: i for i, v in enumerate(nodes)}
    neighbor_mask = [0] * len(nodes)
    for i, v in enumerate(nodes):
        m = 0
        for u in H.neighbors(v):
            m |= 1 << index[u]
        neighbor_mask[i] = m
    n = len(nodes)
    coeffs = [0] * (n + 1)
    def dfs(start, allowed, size):
        coeffs[size] += 1
        i = start
        while i < n:
            bit = 1 << i
            if allowed & bit:
                dfs(i + 1, allowed & ~bit & ~neighbor_mask[i], size + 1)
            i += 1
    dfs(0, (1 << n) - 1, 0)
    while len(coeffs) > 1 and coeffs[-1] == 0:
        coeffs.pop()
    return coeffs


def poly_eval(c: List[int], lam: float) -> float:
    s = 0.0
    for x in reversed(c):
        s = s * lam + x
    return s


# ---------------------------------------------------------------------------
# d-regular tree reference bound (rigorous for ALL d-regular triangle-free).
# rho_tree = 1 - y where  lam * y^{d+1} + y - 1 = 0, y in (0,1).
# This is NOT a valid K4-free bound in general; it *is* for triangle-free.
# Included as a theoretical reference line.
# ---------------------------------------------------------------------------

def rho_tree(d: int, lam: float) -> float:
    """
    Root of  lam * y^(d+1) + y - 1 = 0  in (0,1); returns 1 - y.
    This equals the occupancy fraction at the root of the infinite
    d-regular tree under hard-core at fugacity lam.
    """
    if d == 0:
        # No neighbors: y = 1/(1+lam), rho = lam/(1+lam).
        return lam / (1.0 + lam)
    # Bisection on y
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        val = lam * mid ** (d + 1) + mid - 1.0
        if val > 0:
            hi = mid
        else:
            lo = mid
    y = 0.5 * (lo + hi)
    return 1.0 - y


# ---------------------------------------------------------------------------
# Per-graph exact hard-core occupancy
# ---------------------------------------------------------------------------

def exact_hardcore_bound(G: nx.Graph, lam_grid: np.ndarray) -> dict:
    """
    Exact rho_v(G, lambda) for every v, aggregated over v, evaluated
    on a lambda grid; take the max.
    """
    Zc_G = independence_polynomial(G)
    per_vertex_Zc = []
    for v in G.nodes():
        H = G.copy()
        # remove N[v]
        removal = set(G.neighbors(v)) | {v}
        H.remove_nodes_from(removal)
        per_vertex_Zc.append(independence_polynomial(H))

    # E[|I|](lam) = lam * sum_v Z(G - N[v], lam) / Z(G, lam)
    E_vals = np.zeros_like(lam_grid)
    Zg_vals = np.array([poly_eval(Zc_G, lam) for lam in lam_grid])
    for Zc_v in per_vertex_Zc:
        Zv_vals = np.array([poly_eval(Zc_v, lam) for lam in lam_grid])
        E_vals += lam_grid * Zv_vals / Zg_vals

    best_idx = int(np.argmax(E_vals))
    return dict(
        E_max=float(E_vals[best_idx]),
        lam_star=float(lam_grid[best_idx]),
        Zc_G=Zc_G,
    )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-max", type=int, default=20,
                    help="Process DB graphs with N <= n_max. Exact hard-core "
                         "scales as O(N*2^N); default 20 is safe.")
    ap.add_argument("--lam-min", type=float, default=0.05)
    ap.add_argument("--lam-max", type=float, default=200.0)
    ap.add_argument("--lam-steps", type=int, default=400)
    ap.add_argument("--out-dir", default=os.path.join(REPO, "results", "subplan_b"))
    args = ap.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    lam_grid = np.geomspace(args.lam_min, args.lam_max, args.lam_steps)

    # Pull DB rows
    print(f"[rung2] opening DB (n<={args.n_max}) ...", flush=True)
    with DB(auto_sync=False) as db:
        rows = db.raw_execute(
            "SELECT graph_id, source, n, d_max, alpha, c_log "
            "FROM cache WHERE is_k4_free=1 AND alpha IS NOT NULL AND c_log IS NOT NULL "
            "AND n <= ? ORDER BY n, c_log", (args.n_max,)
        )
        seen = set(); unique = []
        for r in rows:
            if r["graph_id"] not in seen:
                seen.add(r["graph_id"]); unique.append(r)
        print(f"[rung2] {len(unique)} unique K4-free graphs with exact alpha", flush=True)
        hydrated = [(r, db.nx(r["graph_id"])) for r in unique]

    # Read rung 0 output to pair with rung 2
    rung0_path = os.path.join(args.out_dir, "per_graph_bounds.csv")
    rung0_by_gid = {}
    if os.path.exists(rung0_path):
        with open(rung0_path) as f:
            for r in csv.DictReader(f):
                rung0_by_gid[r["graph_id"]] = r

    per_graph = []
    print("[rung2] computing exact hard-core occupancy per graph ...", flush=True)
    for i, (r, G) in enumerate(hydrated):
        N = r["n"]
        alpha = r["alpha"]
        d_max = r["d_max"]
        out = exact_hardcore_bound(G, lam_grid)
        ratio = out["E_max"] / alpha if alpha else None
        r0 = rung0_by_gid.get(r["graph_id"])
        L_HC = float(r0["L_HC"]) if r0 else None
        per_graph.append(dict(
            graph_id=r["graph_id"], n=N, d_max=d_max, alpha=alpha,
            c_log=r["c_log"],
            E_max=out["E_max"], lam_star=out["lam_star"],
            tight_rung2=ratio,
            L_HC_rung0=L_HC,
            c_bound_rung2=(out["E_max"] * d_max / (N * math.log(d_max))) if d_max >= 2 else None,
        ))
        if (i + 1) % 50 == 0:
            print(f"  [{i+1}/{len(hydrated)}] n={N} d_max={d_max} "
                  f"alpha={alpha} E_max={out['E_max']:.2f} "
                  f"(tightness={ratio:.2%})", flush=True)

    # Write CSV
    out_csv = os.path.join(args.out_dir, "rung2_per_graph.csv")
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_graph[0].keys()))
        w.writeheader()
        for row in per_graph:
            w.writerow(row)
    print(f"[rung2] wrote {out_csv}", flush=True)

    # Aggregate per d_max
    by_d = defaultdict(list)
    for r in per_graph:
        by_d[r["d_max"]].append(r)
    agg = []
    for d in sorted(by_d):
        recs = by_d[d]
        tight_mean = float(np.mean([r["tight_rung2"] for r in recs]))
        min_c_r2 = min((r["c_bound_rung2"] for r in recs if r["c_bound_rung2"]), default=None)
        max_c_r2 = max((r["c_bound_rung2"] for r in recs if r["c_bound_rung2"]), default=None)
        min_obs_c = min(r["c_log"] for r in recs)
        agg.append(dict(d_max=d, n=len(recs),
                        mean_tightness_rung2=tight_mean,
                        min_c_bound_rung2=min_c_r2,
                        max_c_bound_rung2=max_c_r2,
                        min_c_log_obs=min_obs_c))
    with open(os.path.join(args.out_dir, "rung2_by_dmax.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agg[0].keys()))
        w.writeheader()
        for row in agg:
            w.writerow(row)
    print(f"[rung2] wrote rung2_by_dmax.csv")

    # Also the tree reference curve (for triangle-free, NOT K4-free)
    tree_ref = []
    for d in range(2, 12):
        # max over lam of rho_tree
        rhos = [rho_tree(d, lam) for lam in lam_grid]
        idx = int(np.argmax(rhos))
        rho = rhos[idx]
        tree_ref.append(dict(d=d, rho_tree=rho, lam=float(lam_grid[idx]),
                             c_bound_tree=rho * d / math.log(d)))
    with open(os.path.join(args.out_dir, "rung2_tree_reference.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(tree_ref[0].keys()))
        w.writeheader()
        for row in tree_ref:
            w.writerow(row)
    print(f"[rung2] wrote rung2_tree_reference.csv")

    # Summary
    print("\n[rung2] summary")
    tightness_all = [r["tight_rung2"] for r in per_graph]
    print(f"  exact rung-2 bound / alpha: mean={np.mean(tightness_all):.2%}, "
          f"max={np.max(tightness_all):.2%}, min={np.min(tightness_all):.2%}")
    print("  This is the ceiling of any hard-core-based method at finite lambda.")
    if per_graph:
        # Best empirical c-bound from rung 2
        valid = [r for r in per_graph if r["c_bound_rung2"]]
        best = max(valid, key=lambda r: r["c_bound_rung2"])
        worst = min(valid, key=lambda r: r["c_bound_rung2"])
        print(f"  best per-graph c_bound_rung2 = {best['c_bound_rung2']:.4f} "
              f"(graph id {best['graph_id'][:8]}, n={best['n']}, d_max={best['d_max']})")
        print(f"  worst per-graph c_bound_rung2 = {worst['c_bound_rung2']:.4f} "
              f"(n={worst['n']}, d_max={worst['d_max']})")


if __name__ == "__main__":
    main()
