#!/usr/bin/env python3
"""
scripts/run_circulant_fast.py
=============================
Sweep CirculantSearchFast across a range of N, capping the connection-set
size. Designed for n up to ~100, where exhaustive CirculantSearch is
infeasible. Saves survivors into graph_db under source="circulant_fast".

Run from repo root::

    micromamba run -n k4free python scripts/run_circulant_fast.py
    micromamba run -n k4free python scripts/run_circulant_fast.py --n-min 10 --n-max 60 --max-size 8
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, CirculantSearchFast


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n-min", type=int, default=10)
    p.add_argument("--n-max", type=int, default=60)
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--max-size", type=int, default=8,
                   help="Upper bound on |S| (default 8).")
    p.add_argument("--min-size", type=int, default=1)
    p.add_argument("--greedy-restarts", type=int, default=40)
    p.add_argument("--save", action="store_true",
                   help="Persist results into graph_db (source=circulant_fast).")
    p.add_argument("--verbosity", type=int, default=1)
    args = p.parse_args()

    summary: list[tuple[int, int, float | None, int, int, float]] = []

    with AggregateLogger(name="circulant_fast_sweep") as agg:
        for n in range(args.n_min, args.n_max + 1):
            t0 = time.monotonic()
            search = CirculantSearchFast(
                n=n,
                top_k=args.top_k,
                max_conn_size=args.max_size,
                min_conn_size=args.min_size,
                greedy_restarts=args.greedy_restarts,
                verbosity=args.verbosity,
                parent_logger=agg,
            )
            results = search.run()
            if args.save:
                search.save(results)
            dt = time.monotonic() - t0
            if results:
                best = results[0]
                summary.append((n, len(results), best.c_log, best.alpha, best.d_max, dt))
                meta = best.metadata or {}
                conn = meta.get("connection_set", [])
                print(f"[circulant_fast n={n:>3}] k={len(results)} "
                      f"best c_log={_fmt(best.c_log)} α={best.alpha} "
                      f"d_max={best.d_max} S={conn} ({dt:.2f}s)")
            else:
                summary.append((n, 0, None, 0, 0, dt))
                print(f"[circulant_fast n={n:>3}] 0 results ({dt:.2f}s)")

    print()
    print("=" * 70)
    print(f"{'n':>4}{'k':>4}{'best c_log':>14}{'alpha':>8}{'d_max':>7}{'t (s)':>10}")
    print("=" * 70)
    for n, k, c, a, d, dt in summary:
        print(f"{n:>4}{k:>4}{_fmt(c):>14}{a:>8}{d:>7}{dt:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
