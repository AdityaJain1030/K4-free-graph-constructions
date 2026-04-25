"""
scripts/run_switch_tabu_mixed_lookahead.py
============================================
Evaluate the mixed-operator switch tabu chain with rollout-based
lookahead as the third ranking layer.

Headline question: at N=23 the plain switch_tabu plateaus at α=7
(10/10 in prior runs). Does adding lookahead break the α=7 → α=6 wall?

The driver mirrors `run_switch_tabu.py` so the comparison is line-for-
line. Two ablation modes:
  --modes baseline           # mixed chain WITHOUT lookahead (lookahead_top_k=0)
  --modes lookahead          # mixed chain WITH lookahead
  --modes baseline lookahead # both, head-to-head
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.switch_tabu import SwitchTabuMixedLookaheadSearch
from graph_db.db import DB


# Frontier rows (from graph_db SAT-certified).
FRONTIER = {
    14: (3, 6, 0.7176, "sat (3,6)"),
    15: (3, 7, 0.7195, "sat (3,7)"),
    23: (6, 4, 0.7527, "sat (6,4) — α=6 below tabu plateau"),
}


def _frontier_adj(n: int) -> np.ndarray | None:
    with DB() as db:
        rows = [r for r in db.query(n=n) if r["c_log"] is not None]
        rows.sort(key=lambda r: r["c_log"])
        if not rows:
            return None
        G = db.nx(rows[0]["graph_id"])
        return None if G is None else np.array(nx.to_numpy_array(G, dtype=np.uint8))


def _run_one(n: int, *, mode: str, args, seed_offset: int):
    front = FRONTIER.get(n)
    d_target = front[1] if front else None
    c_front = front[2] if front else None
    ref = front[3] if front else "?"

    is_warm = mode.startswith("warm_")
    warm_adj = _frontier_adj(n) if is_warm else None
    if is_warm and warm_adj is None:
        return None

    # Mode flags. Lookahead and 3-switches are independent toggles.
    use_lookahead = "lookahead" in mode
    use_swap3 = "swap3" in mode
    lookahead_top_k = args.lookahead_top_k if use_lookahead else 0
    sample_size_swap3 = args.sample_size_swap3 if use_swap3 else 0
    # If we're using both, the lookahead rollouts also include 3-switches
    # so the probe matches the chain's actual reach.
    lookahead_p_swap3 = args.lookahead_p_swap3 if (use_lookahead and use_swap3) else 0.0

    search = SwitchTabuMixedLookaheadSearch(
        n=n,
        d_target=d_target,
        n_restarts=args.n_restarts,
        n_iters=args.n_iters,
        sample_size_swap=args.sample_size_swap,
        sample_size_flip=args.sample_size_flip,
        sample_size_swap3=sample_size_swap3,
        swap3_novel_only=args.swap3_novel_only,
        top_k_verify=args.top_k_verify,
        lookahead_top_k=lookahead_top_k,
        lookahead_h=args.lookahead_h,
        lookahead_M=args.lookahead_M,
        lookahead_p_flip=args.lookahead_p_flip,
        lookahead_p_swap3=lookahead_p_swap3,
        lb_restarts=args.lb_restarts,
        patience=args.patience,
        perturb_swaps=args.perturb_swaps,
        spread_cap=args.spread_cap,
        time_limit_s=args.time_limit_s,
        random_seed=args.seed + n + seed_offset,
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
    p.add_argument("--ns", type=int, nargs="+", default=[23])
    p.add_argument(
        "--modes", nargs="+",
        choices=[
            "baseline", "lookahead", "swap3", "swap3_lookahead",
            "warm_baseline", "warm_lookahead", "warm_swap3", "warm_swap3_lookahead",
        ],
        default=["baseline", "swap3", "lookahead", "swap3_lookahead"],
        help="Mode names compose toggles: 'lookahead' enables rollout-rerank; 'swap3' enables 3-switch move; 'warm_' inits at the SAT frontier.",
    )
    p.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2, 3])
    p.add_argument("--n_restarts", type=int, default=1)
    p.add_argument("--n_iters", type=int, default=400)
    p.add_argument("--sample_size_swap", type=int, default=80)
    p.add_argument("--sample_size_flip", type=int, default=40)
    p.add_argument("--sample_size_swap3", type=int, default=80)
    p.add_argument("--swap3_novel_only", action="store_true")
    p.add_argument("--top_k_verify", type=int, default=6)
    p.add_argument("--lookahead_top_k", type=int, default=5)
    p.add_argument("--lookahead_h", type=int, default=4)
    p.add_argument("--lookahead_M", type=int, default=5)
    p.add_argument("--lookahead_p_flip", type=float, default=0.5)
    p.add_argument("--lookahead_p_swap3", type=float, default=0.3)
    p.add_argument("--lb_restarts", type=int, default=12)
    p.add_argument("--patience", type=int, default=60)
    p.add_argument("--perturb_swaps", type=int, default=5)
    p.add_argument("--spread_cap", type=int, default=1)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--time_limit_s", type=float, default=180.0)
    p.add_argument("--verbosity", type=int, default=0)
    args = p.parse_args()

    print(
        f"{'mode':>22} {'N':>3} {'seed':>4} {'d*':>3} {'α':>3} {'c_log':>9} "
        f"{'frontier':>9} {'gap':>9} {'la_min':>9} {'disagree':>9} "
        f"{'sw3 (n/e)':>10} {'elapsed_s':>10}  info"
    )
    print("-" * 145)

    # Aggregation buckets per (mode, N) for the post-table summary.
    buckets: dict[tuple[str, int], list] = {}

    for n in args.ns:
        for mode in args.modes:
            for seed in args.seeds:
                r = _run_one(n, mode=mode, args=args, seed_offset=seed)
                if r is None:
                    print(
                        f"{mode:>22} {n:>3} {seed:>4} {'-':>3} {'-':>3} {'-':>9} "
                        f"{'-':>9} {'-':>9} {'-':>9} {'-':>9} {'-':>10} {'-':>10}  no frontier"
                    )
                    continue
                results, elapsed, c_front, ref, d_target = r
                if not results:
                    print(
                        f"{mode:>22} {n:>3} {seed:>4} {str(d_target):>3} {'-':>3} "
                        f"{'-':>9} {c_front:>9.4f} {'-':>9} {'-':>9} {'-':>9} "
                        f"{'-':>10} {elapsed:>10.1f}  no result"
                    )
                    continue
                res = results[0]
                meta = res.metadata
                la_min = meta.get("lookahead_min_c_log_seen")
                la_min_str = "-" if la_min is None else f"{la_min:.4f}"
                disagree = meta.get("lookahead_n_disagree", 0)
                la_iters = meta.get("lookahead_n_iters", 0) or 1
                disagree_str = f"{disagree}/{la_iters}"
                sw3_n = meta.get("swap3_accepted_novel", 0)
                sw3_e = meta.get("swap3_accepted_equiv", 0)
                sw3_str = f"{sw3_n}/{sw3_e}" if (sw3_n + sw3_e) > 0 else "-"
                c_str = "-" if res.c_log is None else f"{res.c_log:.4f}"
                gap_str = "-"
                if c_front is not None and res.c_log is not None:
                    gap_str = f"{res.c_log - c_front:+.4f}"
                print(
                    f"{mode:>22} {n:>3} {seed:>4} {str(d_target):>3} {res.alpha:>3} "
                    f"{c_str:>9} {c_front:>9.4f} {gap_str:>9} {la_min_str:>9} "
                    f"{disagree_str:>9} {sw3_str:>10} {elapsed:>10.1f}  vs {ref}"
                )
                buckets.setdefault((mode, n), []).append((res.alpha, res.c_log, elapsed))

    # Summary across seeds.
    if buckets:
        print()
        print("Summary (per mode × N, across seeds):")
        print(f"  {'mode':>22} {'N':>3} {'n':>3} {'α distribution':>22} "
              f"{'c_log min':>10} {'c_log med':>10} {'wall sum':>10}")
        for (mode, n), runs in sorted(buckets.items()):
            from collections import Counter
            import statistics
            alphas = [r[0] for r in runs]
            cs = [r[1] for r in runs if r[1] is not None]
            walls = [r[2] for r in runs]
            adist = dict(Counter(alphas))
            cmin = f"{min(cs):.4f}" if cs else "-"
            cmed = f"{statistics.median(cs):.4f}" if cs else "-"
            print(f"  {mode:>22} {n:>3} {len(runs):>3} {str(adist):>22} "
                  f"{cmin:>10} {cmed:>10} {sum(walls):>10.1f}")


if __name__ == "__main__":
    main()
