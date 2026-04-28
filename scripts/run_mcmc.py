"""
scripts/run_mcmc.py
====================
Smoke / frontier-comparison driver for `search.mcmc.MCMCSearch`.

For each (N, β), run a few independent MH chains from a cold random
near-regular K4-free init and report the best c_log against the SAT-
certified frontier in graph_db. Mirrors `run_switch_tabu.py` so the
two methods are comparable line-for-line.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.stochastic_walk.mcmc import MCMCSearch
from search.stochastic_walk.switch_tabu import _build_multiset_init
from graph_db.db import DB


# Known SAT-certified frontier rows + their degree multisets.
# The 2-switch chain is partitioned by degree multiset — it can only
# reach the optimum if init lives in the matching class. We use
# `_build_multiset_init` to seed the chain in the right basin.
FRONTIER = {
    14: {
        "alpha": 3, "d_max": 6, "c_log": 0.7176,
        "ref": "sat_exact (3,6)",
        "degs": [6] * 12 + [5] * 2,
    },
    15: {
        "alpha": 3, "d_max": 7, "c_log": 0.7195,
        "ref": "sat_exact (3,7)",
        "degs": [7] * 12 + [6] * 3,
    },
    23: {
        "alpha": 6, "d_max": 4, "c_log": 0.7527,
        "ref": "sat (6,4) — α=6 below tabu plateau",
        "degs": [4] * 19 + [3] * 4,
    },
}


def _frontier_adj(n: int) -> np.ndarray | None:
    """Top-1 c_log-defined graph at N from graph_db, as adjacency matrix."""
    with DB() as db:
        rows = [r for r in db.query(n=n) if r["c_log"] is not None]
        rows.sort(key=lambda r: r["c_log"])
        if not rows:
            return None
        G = db.nx(rows[0]["graph_id"])
        if G is None:
            return None
        return np.array(nx.to_numpy_array(G, dtype=np.uint8))


def _run_one(n: int, *, mode: str, args, beta: float):
    """
    mode ∈ {"cold_dreg", "cold_multiset", "warm"}:
      cold_dreg     — random near-regular K4-free init at d_target
      cold_multiset — random init constrained to the frontier degree
                      multiset (so 2-switch can in principle reach the
                      optimum); falls back to cold_dreg if build fails
      warm          — start at the SAT-certified frontier graph itself
                      (sanity check: chain should stay near it)
    """
    front = FRONTIER.get(n)
    d_target = front["d_max"] if front is not None else None
    c_front = front["c_log"] if front is not None else None
    ref = front["ref"] if front is not None else "?"

    init_adj = None
    if mode == "warm":
        init_adj = _frontier_adj(n)
        if init_adj is None:
            return None
    elif mode == "cold_multiset":
        if front is None:
            return None
        seed_rng = np.random.default_rng(args.seed + n + int(beta * 13))
        init_adj = _build_multiset_init(n, front["degs"], seed_rng)
        # If the multiset build failed, fall back to d-regular init
        if init_adj is None or init_adj.sum() == 0:
            init_adj = None

    search = MCMCSearch(
        n=n,
        d_target=d_target,
        n_restarts=args.n_restarts,
        n_iters=args.n_iters,
        beta=beta,
        time_limit_s=args.time_limit_s,
        random_seed=args.seed + n + (100 if mode == "warm" else 0) + int(beta * 13),
        verbosity=args.verbosity,
        log_every=args.log_every,
        top_k=1,
        warm_start_adj=init_adj,
    )
    t0 = time.monotonic()
    results = search.run()
    elapsed = time.monotonic() - t0
    return results, elapsed, c_front, ref, d_target


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ns", type=int, nargs="+", default=[14, 15, 23])
    p.add_argument("--betas", type=float, nargs="+", default=[20.0])
    p.add_argument("--n_restarts", type=int, default=4)
    p.add_argument("--n_iters", type=int, default=5000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--time_limit_s", type=float, default=120.0)
    p.add_argument("--verbosity", type=int, default=0)
    p.add_argument("--log_every", type=int, default=0)
    p.add_argument(
        "--modes", nargs="+",
        choices=["cold_dreg", "cold_multiset", "warm"],
        default=["cold_multiset", "warm"],
    )
    args = p.parse_args()

    print(
        f"{'mode':>14} {'N':>3} {'β':>5} {'d*':>3} {'α':>3} {'c_log':>9} "
        f"{'frontier':>9} {'gap':>9} {'elapsed_s':>10}  info"
    )
    print("-" * 110)

    for n in args.ns:
        for beta in args.betas:
            for mode in args.modes:
                r = _run_one(n, mode=mode, args=args, beta=beta)
                if r is None:
                    print(
                        f"{mode:>14} {n:>3} {beta:>5.1f} {'-':>3} {'-':>3} {'-':>9} "
                        f"{'-':>9} {'-':>9} {'-':>10}  no frontier in graph_db"
                    )
                    continue
                results, elapsed, c_front, ref, d_target = r
                if not results:
                    print(
                        f"{mode:>14} {n:>3} {beta:>5.1f} {str(d_target):>3} {'-':>3} "
                        f"{'-':>9} {c_front:>9.4f} {'-':>9} {elapsed:>10.1f}  no result"
                    )
                    continue
                res = results[0]
                c_str = "-" if res.c_log is None else f"{res.c_log:.4f}"
                gap_str = "-"
                if c_front is not None and res.c_log is not None:
                    gap_str = f"{res.c_log - c_front:+.4f}"
                print(
                    f"{mode:>14} {n:>3} {beta:>5.1f} {str(d_target):>3} {res.alpha:>3} "
                    f"{c_str:>9} {c_front:>9.4f} {gap_str:>9} {elapsed:>10.1f}  "
                    f"vs {ref}"
                )


if __name__ == "__main__":
    main()
