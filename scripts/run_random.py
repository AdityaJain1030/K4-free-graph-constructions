#!/usr/bin/env python3
"""
scripts/run_random.py
=====================
Run the RandomSearch baseline for n=10..30 under one AggregateLogger.
Saves results into graph_db and prints a per-N summary.

Run from repo root::

    micromamba run -n k4free python scripts/run_random.py
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, RandomSearch


N_RANGE = range(10, 31)  # inclusive 10..30
TOP_K = 3


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    summary: list[tuple[int, int, float | None, int, int, float]] = []

    with AggregateLogger(name="random_sweep") as agg:
        for n in N_RANGE:
            t0 = time.monotonic()
            search = RandomSearch(n=n, top_k=TOP_K, verbosity=1, parent_logger=agg)
            results = search.run()
            search.save(results)
            dt = time.monotonic() - t0
            if results:
                best = results[0]
                summary.append((n, len(results), best.c_log, best.alpha, best.d_max, dt))
                print(f"[random n={n:>2}] {len(results)} results, "
                      f"best c_log={_fmt(best.c_log)}  α={best.alpha}  d_max={best.d_max}  "
                      f"({dt:.2f}s)")
            else:
                summary.append((n, 0, None, 0, 0, dt))
                print(f"[random n={n:>2}] 0 results  ({dt:.2f}s)")

    print()
    print("=" * 70)
    print(f"{'n':>4}{'k':>4}{'best c_log':>14}{'alpha':>8}{'d_max':>7}{'t (s)':>9}")
    print("=" * 70)
    for n, k, c, a, d, dt in summary:
        print(f"{n:>4}{k:>4}{_fmt(c):>14}{a:>8}{d:>7}{dt:>9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
