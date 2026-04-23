#!/usr/bin/env python3
"""
scripts/run_cayley_tabu_polarity_ns.py
=======================================
Run Cayley-tabu at the N values coming from ER polarity at
q ∈ {11, 13, 16, 17, 19, 23} — i.e. N ∈ {133, 183, 273, 307, 381, 553}.

Uses the existing `CayleyTabuSearch` so the usual cost function
(α_lb · d / (n · ln d), hard K4-free constraint) is reused. At each
N the default family iterator picks every supported abelian/dihedral
decomposition; we don't restrict to Z_N specifically because the
direct-product families (e.g. Z_7 × Z_19 at N=133) sometimes beat
the plain cyclic group.

Results get ingested under source='cayley_tabu' via Search.save().
"""

from __future__ import annotations

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import CayleyTabuSearch, AggregateLogger


TARGETS = [
    (11, 133),
    (13, 183),
    (16, 273),
    (17, 307),
    (19, 381),
    (23, 553),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qs", type=int, nargs="+", default=None,
                    help="restrict to these q values; default: all")
    ap.add_argument("--n-iters", type=int, default=200)
    ap.add_argument("--n-restarts", type=int, default=3)
    ap.add_argument("--lb-restarts", type=int, default=24)
    ap.add_argument("--time-limit-s", type=float, default=600.0,
                    help="wall clock per (N, group)")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    targets = TARGETS if args.qs is None else [t for t in TARGETS if t[0] in args.qs]

    with AggregateLogger(name="cayley_tabu_polarity_ns") as agg:
        for q, n in targets:
            t0 = time.monotonic()
            print(f"\n=== N={n} (q={q}) ===", flush=True)
            search = CayleyTabuSearch(
                n=n,
                top_k=1,
                verbosity=1,
                parent_logger=agg,
                n_iters=args.n_iters,
                n_restarts=args.n_restarts,
                lb_restarts=args.lb_restarts,
                time_limit_s=args.time_limit_s,
                random_seed=args.seed,
            )
            results = search.run()
            search.save([r for r in results if r.is_k4_free])
            dt = time.monotonic() - t0
            if results:
                r = results[0]
                print(f"  [result] c_log={r.c_log:.6f}  α={r.alpha}  "
                      f"d_max={r.d_max}  k4_free={r.is_k4_free}  ({dt:.1f}s)",
                      flush=True)
            else:
                print(f"  [no result] ({dt:.1f}s)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
