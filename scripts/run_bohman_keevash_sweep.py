"""
scripts/run_bohman_keevash_sweep.py
====================================
Sweep the Bohman-Keevash random K4-free process over N=10..100.

For each N: run num_trials independent B-K runs, keep the top result by
c_log, compute the local rung-0 hard-core tightness on the best output,
and persist to graph_db under source="bohman_keevash".

Writes results/bohman_keevash_sweep.csv with one row per N (best output
+ per-N statistics over trials).
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np
import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search.bohman_keevash import BohmanKeevashSearch
from graph_db import DB


# ---- local rung-0 hard-core lower bound on E_max -------------------------------

def indep_poly(H: nx.Graph) -> list[int]:
    nodes = list(H.nodes())
    if not nodes:
        return [1]
    nodes.sort(key=lambda v: -H.degree(v))
    idx = {v: i for i, v in enumerate(nodes)}
    nbr = [0] * len(nodes)
    for i, v in enumerate(nodes):
        m = 0
        for u in H.neighbors(v):
            m |= 1 << idx[u]
        nbr[i] = m
    n = len(nodes)
    c = [0] * (n + 1)

    def dfs(start, allowed, sz):
        c[sz] += 1
        i = start
        while i < n:
            bit = 1 << i
            if allowed & bit:
                dfs(i + 1, allowed & ~bit & ~nbr[i], sz + 1)
            i += 1

    dfs(0, (1 << n) - 1, 0)
    while len(c) > 1 and c[-1] == 0:
        c.pop()
    return c


def poly_eval(c, lam):
    s = 0.0
    for x in reversed(c):
        s = s * lam + x
    return s


LAM = np.geomspace(0.05, 500.0, 300)


def local_hc_bound(G: nx.Graph) -> float:
    E = np.zeros_like(LAM)
    for v in G.nodes():
        Tv = G.subgraph(list(G.neighbors(v))).copy()
        Zt = np.array([poly_eval(indep_poly(Tv), l) for l in LAM])
        E += LAM / (LAM + Zt)
    return float(E.max())


# ---- driver --------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=100)
    ap.add_argument("--trials", type=int, default=50)
    ap.add_argument("--seed", type=int, default=20260424)
    ap.add_argument("--out-csv", default=os.path.join(REPO, "results", "bohman_keevash_sweep.csv"))
    ap.add_argument("--save-db", action="store_true", default=True)
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out_csv), exist_ok=True)

    rows = []
    t_start = time.time()
    for n in range(args.n_min, args.n_max + 1):
        t0 = time.time()
        s = BohmanKeevashSearch(n=n, num_trials=args.trials, top_k=args.trials, seed=args.seed)
        results = s.run()
        if not results:
            continue
        best = results[0]
        c_logs = [r.c_log for r in results if r.c_log is not None]
        d_maxs = [r.d_max for r in results]
        alphas = [r.alpha for r in results]
        ms = [r.G.number_of_edges() for r in results]

        E_loc = local_hc_bound(best.G)
        tight = E_loc / best.alpha if best.alpha else None

        rows.append({
            "n": n,
            "trials": len(results),
            "best_c_log": best.c_log,
            "best_alpha": best.alpha,
            "best_d_max": best.d_max,
            "best_m": best.G.number_of_edges(),
            "mean_c_log": float(np.mean(c_logs)),
            "median_c_log": float(np.median(c_logs)),
            "std_c_log": float(np.std(c_logs)),
            "min_d_max": int(np.min(d_maxs)),
            "max_d_max": int(np.max(d_maxs)),
            "median_d_max": float(np.median(d_maxs)),
            "mean_alpha": float(np.mean(alphas)),
            "mean_m": float(np.mean(ms)),
            "E_local_hc_best": E_loc,
            "hc_tightness_lb_best": tight,
            "elapsed_s": time.time() - t0,
        })
        print(f"  N={n:>3}  best c_log={best.c_log:.4f}  α={best.alpha:>3} d_max={best.d_max:>3} m={best.G.number_of_edges():>5}"
              f"  median c_log={np.median(c_logs):.4f}  E_loc/α≥{tight:.3f}  ({time.time()-t0:.1f}s)",
              flush=True)

        if args.save_db:
            try:
                s.save([best])
            except Exception as e:
                print(f"    [save] skip: {e}")

    cols = list(rows[0].keys())
    with open(args.out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\n[bk-sweep] wrote {args.out_csv} ({len(rows)} rows, total {time.time()-t_start:.1f}s)")


if __name__ == "__main__":
    main()
