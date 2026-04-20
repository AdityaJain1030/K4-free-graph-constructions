#!/usr/bin/env python3
"""
scripts/run_norm_graph.py
=========================
Run NormGraphSearch (Probe 5b) over eligible N = q² − 1 for prime q.

Run from repo root::

    micromamba run -n k4free python scripts/run_norm_graph.py
"""

import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, NormGraphSearch


# Primes q → N = q^2 - 1
TARGET_NS = [
    3 * 3 - 1,     # 8
    5 * 5 - 1,     # 24
    7 * 7 - 1,     # 48
    11 * 11 - 1,   # 120
    13 * 13 - 1,   # 168
]


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-n", type=int, default=150,
                    help="upper cap on N. Sparse algebraic; 150 by default.")
    args = ap.parse_args()

    ns = [n for n in TARGET_NS if n <= args.max_n]

    summary = []
    with AggregateLogger(name="norm_graph_sweep") as agg:
        for n in ns:
            t0 = time.monotonic()
            search = NormGraphSearch(n=n, verbosity=1, parent_logger=agg)
            results = search.run()
            search.save([r for r in results if r.is_k4_free])
            dt = time.monotonic() - t0
            if results:
                r = results[0]
                summary.append((n, r.c_log, r.alpha, r.d_max, r.is_k4_free, dt))
                print(f"[norm_graph n={n:>4}] c_log={_fmt(r.c_log)} α={r.alpha} "
                      f"d_max={r.d_max} k4_free={r.is_k4_free} ({dt:.2f}s)")
            else:
                print(f"[norm_graph n={n:>4}] skipped ({dt:.2f}s)")

    print()
    print("=" * 72)
    print(f"{'n':>5}{'c_log':>14}{'α':>6}{'d_max':>7}{'k4':>5}{'t (s)':>9}")
    print("=" * 72)
    for n, c, a, d, k4, dt in summary:
        print(f"{n:>5}{_fmt(c):>14}{a:>6}{d:>7}{int(k4):>5}{dt:>9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
