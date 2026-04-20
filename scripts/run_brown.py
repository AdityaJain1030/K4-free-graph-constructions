#!/usr/bin/env python3
"""
scripts/run_brown.py
====================
Run BrownSearch (Probe 5c) over eligible N = q³ for small odd prime q.

Default sweep only runs q ∈ {5, 7}. Larger q are gated behind --large
because the α exact-solver cost grows quickly (q = 11 gives N = 1331).

Run from repo root::

    micromamba run -n k4free python scripts/run_brown.py
    micromamba run -n k4free python scripts/run_brown.py --large
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, BrownSearch


SMALL = [5 ** 3]                      # 125 (sparse algebraic, within 150 cap)
LARGE = [5 ** 3, 7 ** 3, 11 ** 3]     # 125, 343, 1331 — server only


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--large", action="store_true",
                    help="include q=11 (N=1331). Skip on local box; server only.")
    args = ap.parse_args()

    ns = LARGE if args.large else SMALL
    summary = []
    with AggregateLogger(name="brown_sweep") as agg:
        for n in ns:
            t0 = time.monotonic()
            search = BrownSearch(n=n, verbosity=1, parent_logger=agg)
            results = search.run()
            search.save([r for r in results if r.is_k4_free])
            dt = time.monotonic() - t0
            if results:
                r = results[0]
                summary.append((n, r.c_log, r.alpha, r.d_max, r.is_k4_free, dt))
                print(f"[brown n={n:>5}] c_log={_fmt(r.c_log)} α={r.alpha} "
                      f"d_max={r.d_max} k4_free={r.is_k4_free} ({dt:.2f}s)")
            else:
                print(f"[brown n={n:>5}] skipped ({dt:.2f}s)")

    print()
    print("=" * 72)
    print(f"{'n':>6}{'c_log':>14}{'α':>6}{'d_max':>7}{'k4':>5}{'t (s)':>9}")
    print("=" * 72)
    for n, c, a, d, k4, dt in summary:
        print(f"{n:>6}{_fmt(c):>14}{a:>6}{d:>7}{int(k4):>5}{dt:>9.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
