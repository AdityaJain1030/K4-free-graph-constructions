"""
scripts/run_switch_tabu.py
===========================
Smoke test + frontier comparison for search.switch_tabu.SwitchTabuSearch.

For each (N, d_target), run a short tabu with a handful of restarts and
print the best c_log found vs. the known frontier best for that N. We
don't persist to graph_db here — this is just a what-does-it-find probe.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.switch_tabu import SwitchTabuSearch
from graph_db.db import DB


# Known best c_log for quick comparison (from graph_db top-1).
FRONTIER = {
    14: (3, 6, 0.717571, "sat_exact (near-reg)"),
    17: (3, 8, 0.678915, "P(17) Paley"),
    20: (4, 7, 0.719458, "Cayley D10 / SAT"),
    22: (4, 8, 0.699489, "C(22) Cayley"),
}


def _frontier_adj(n: int) -> np.ndarray | None:
    """Fetch top-1 graph at this N from graph_db as an adjacency matrix."""
    with DB() as db:
        rows = db.top("c_log", k=1, ascending=True, n=n)
        if not rows:
            return None
        G = db.nx(rows[0]["graph_id"])
        if G is None:
            return None
        return np.array(nx.to_numpy_array(G, dtype=np.uint8))


def _run_one(n, *, warm: bool, args):
    _, d_target, c_front, ref = FRONTIER.get(n, (None, None, None, "?"))
    warm_adj = _frontier_adj(n) if warm else None
    if warm and warm_adj is None:
        return None

    search = SwitchTabuSearch(
        n=n,
        d_target=d_target,
        n_restarts=args.n_restarts,
        n_iters=args.n_iters,
        sample_size=args.sample_size,
        top_k_verify=args.top_k_verify,
        lb_restarts=args.lb_restarts,
        patience=args.patience,
        perturb_swaps=args.perturb_swaps,
        time_limit_s=args.time_limit_s,
        random_seed=args.seed + n + (100 if warm else 0),
        verbosity=args.verbosity,
        top_k=1,
        warm_start_adj=warm_adj,
    )
    t0 = time.monotonic()
    results = search.run()
    elapsed = time.monotonic() - t0
    return results, elapsed, c_front, ref, d_target


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ns", type=int, nargs="+", default=[17, 20, 22])
    p.add_argument("--n_restarts", type=int, default=4)
    p.add_argument("--n_iters", type=int, default=400)
    p.add_argument("--sample_size", type=int, default=80)
    p.add_argument("--top_k_verify", type=int, default=6)
    p.add_argument("--lb_restarts", type=int, default=12)
    p.add_argument("--patience", type=int, default=50)
    p.add_argument("--perturb_swaps", type=int, default=6)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--time_limit_s", type=float, default=90.0)
    p.add_argument("--verbosity", type=int, default=0)
    p.add_argument("--mode", choices=["cold", "warm", "both"], default="both")
    args = p.parse_args()

    print(f"{'mode':>4} {'N':>3} {'d*':>3} {'α':>3} {'c_log':>9} {'frontier':>9} "
          f"{'gap':>9}  {'elapsed_s':>10}  info")
    print("-" * 95)

    modes = ["cold", "warm"] if args.mode == "both" else [args.mode]
    for n in args.ns:
        for mode in modes:
            r = _run_one(n, warm=(mode == "warm"), args=args)
            if r is None:
                print(f"{mode:>4} {n:>3} {'-':>3} {'-':>3} {'-':>9} {'-':>9} "
                      f"{'-':>9} {'-':>10}  no frontier row in graph_db")
                continue
            results, elapsed, c_front, ref, d_target = r
            if not results:
                print(f"{mode:>4} {n:>3} {str(d_target):>3} {'-':>3} {'-':>9} "
                      f"{c_front:>9.4f} {'-':>9} {elapsed:>10.1f}  no result ({ref})")
                continue
            res = results[0]
            c_str = "-" if res.c_log is None else f"{res.c_log:.4f}"
            gap_str = "-"
            if c_front is not None and res.c_log is not None:
                gap = res.c_log - c_front
                gap_str = f"{gap:+.4f}"
            print(f"{mode:>4} {n:>3} {str(d_target):>3} {res.alpha:>3} "
                  f"{c_str:>9} {c_front:>9.4f} {gap_str:>9} {elapsed:>10.1f}  "
                  f"vs {ref}")


if __name__ == "__main__":
    main()
