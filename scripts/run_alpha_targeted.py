#!/usr/bin/env python3
"""
scripts/run_alpha_targeted.py
=============================
Run AlphaTargetedSearch (Method 2: α-targeted stochastic local search)
across a chosen N range under one AggregateLogger. Saves results into
graph_db.

Local-box defaults are small; the wider sweep is a server workload (see
memory/env_hardware.md).

Run from repo root::

    micromamba run -n k4free python scripts/run_alpha_targeted.py
    micromamba run -n k4free python scripts/run_alpha_targeted.py --preset local100
    micromamba run -n k4free python scripts/run_alpha_targeted.py --preset large
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, AlphaTargetedSearch


PRESETS = {
    # (n_range, num_trials, num_steps)
    "quick":    (range(15, 31, 5), 3,  80),
    "default":  (range(20, 41, 5), 4, 150),
    "local100": ([20, 30, 40, 50, 60, 70, 80, 100], 4, 200),
    "large":    ([40, 50, 60, 70, 80, 100], 10, 400),
}


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", choices=PRESETS.keys(), default="default")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--alpha-restarts", type=int, default=64)
    ap.add_argument("--pair-attempts", type=int, default=40)
    ap.add_argument("--remove-attempts", type=int, default=30)
    ap.add_argument("--max-degree-spread", type=int, default=2)
    ap.add_argument("--stall-cap", type=int, default=30)
    args = ap.parse_args()

    ns, num_trials, num_steps = PRESETS[args.preset]
    summary = []

    with AggregateLogger(name=f"alpha_targeted_{args.preset}") as agg:
        for n in ns:
            t0 = time.monotonic()
            search = AlphaTargetedSearch(
                n=n,
                top_k=args.top_k,
                verbosity=1,
                parent_logger=agg,
                num_trials=num_trials,
                num_steps=num_steps,
                stall_cap=args.stall_cap,
                alpha_restarts=args.alpha_restarts,
                pair_attempts=args.pair_attempts,
                remove_attempts=args.remove_attempts,
                max_degree_spread=args.max_degree_spread,
                seed=args.seed,
            )
            results = search.run()
            search.save([r for r in results if r.is_k4_free])
            dt = time.monotonic() - t0
            if results:
                best = results[0]
                summary.append((n, len(results), best.c_log, best.alpha, best.d_max, dt))
                print(f"[alpha_targeted n={n:>3}] {len(results)} results  "
                      f"best c_log={_fmt(best.c_log)}  α={best.alpha}  d_max={best.d_max}  "
                      f"({dt:.2f}s)")
            else:
                summary.append((n, 0, None, 0, 0, dt))
                print(f"[alpha_targeted n={n:>3}] 0 results  ({dt:.2f}s)")

    print()
    print("=" * 70)
    print(f"{'n':>4}{'k':>4}{'best c_log':>14}{'alpha':>8}{'d_max':>7}{'t (s)':>9}")
    print("=" * 70)
    for n, k, c, a, d, dt in summary:
        print(f"{n:>4}{k:>4}{_fmt(c):>14}{a:>8}{d:>7}{dt:>9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
