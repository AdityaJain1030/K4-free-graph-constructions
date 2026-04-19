#!/usr/bin/env python3
"""
scripts/run_regularity_alpha.py
===============================
Run the RegularityAlphaSearch baseline for n=10..30 under one
AggregateLogger. Prints a per-N summary. Does NOT save to graph_db by
default — pass `--save` to persist.

Run from repo root::

    micromamba run -n k4free python scripts/run_regularity_alpha.py
    micromamba run -n k4free python scripts/run_regularity_alpha.py --save
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, RegularityAlphaSearch


N_RANGE = range(10, 31)
TOP_K = 3


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--save", action="store_true",
                        help="persist results into graph_db")
    args = parser.parse_args()

    summary: list[tuple[int, int, float | None, int, int, float]] = []

    with AggregateLogger(name="regularity_alpha_sweep") as agg:
        for n in N_RANGE:
            t0 = time.monotonic()
            search = RegularityAlphaSearch(n=n, top_k=TOP_K, verbosity=1,
                                           parent_logger=agg)
            results = search.run()
            if args.save:
                search.save(results)
            dt = time.monotonic() - t0
            if results:
                best = results[0]
                summary.append((n, len(results), best.c_log, best.alpha,
                                best.d_max, dt))
                print(f"[regularity_alpha n={n:>2}] {len(results)} results, "
                      f"best c_log={_fmt(best.c_log)}  α={best.alpha}  "
                      f"d_max={best.d_max}  ({dt:.2f}s)")
            else:
                summary.append((n, 0, None, 0, 0, dt))
                print(f"[regularity_alpha n={n:>2}] 0 results  ({dt:.2f}s)")

    print()
    print("=" * 70)
    print(f"{'n':>4}{'k':>4}{'best c_log':>14}{'alpha':>8}{'d_max':>7}{'t (s)':>9}")
    print("=" * 70)
    for n, k, c, a, d, dt in summary:
        print(f"{n:>4}{k:>4}{_fmt(c):>14}{a:>8}{d:>7}{dt:>9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
