#!/usr/bin/env python3
"""
scripts/run_mattheus_verstraete.py
===================================
Run the Mattheus–Verstraete Hq* construction as a baseline across valid
n values (= q²(q²−q+1) for prime q). Saves into graph_db and prints a
per-N summary.

    micromamba run -n k4free python scripts/run_mattheus_verstraete.py
    micromamba run -n k4free python scripts/run_mattheus_verstraete.py --full
    micromamba run -n k4free python scripts/run_mattheus_verstraete.py --xlarge

Default sweep is {n=12, n=63}. `--full` adds n=525 (α may take minutes).
`--xlarge` adds n=2107 (α likely infeasible with alpha_exact_nx).
"""

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, MattheusVerstraeteSearch


_DEFAULT_NS = [12, 63]
_FULL_NS = [12, 63, 525]
_XLARGE_NS = [12, 63, 525, 2107]

TOP_K = 3


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--full", action="store_true",
                    help="include n=525 (q=5); α computation can take minutes")
    ap.add_argument("--xlarge", action="store_true",
                    help="include n=2107 (q=7); α likely infeasible with current solver")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if args.xlarge:
        ns = _XLARGE_NS
        print("[warn] --xlarge includes n=2107; alpha_exact_nx is likely to hang.")
    elif args.full:
        ns = _FULL_NS
    else:
        ns = _DEFAULT_NS

    summary: list[tuple[int, int, int, float | None, int, int, float]] = []

    with AggregateLogger(name="mv_sweep") as agg:
        for n in ns:
            t0 = time.monotonic()
            search = MattheusVerstraeteSearch(
                n=n, top_k=TOP_K, verbosity=1,
                parent_logger=agg, seed=args.seed,
            )
            results = search.run()
            search.save(results)
            dt = time.monotonic() - t0
            q = search.q
            if results:
                best = results[0]
                summary.append((n, q, len(results), best.c_log,
                                best.alpha, best.d_max, dt))
                print(f"[mv n={n:>4} q={q}] {len(results)} results, "
                      f"best c_log={_fmt(best.c_log)}  α={best.alpha}  d_max={best.d_max}  "
                      f"({dt:.2f}s)")
            else:
                summary.append((n, q, 0, None, 0, 0, dt))
                print(f"[mv n={n:>4} q={q}] 0 results  ({dt:.2f}s)")

    print()
    print("=" * 74)
    print(f"{'n':>5}{'q':>3}{'k':>4}{'best c_log':>14}{'alpha':>8}{'d_max':>7}{'t (s)':>10}")
    print("=" * 74)
    for n, q, k, c, a, d, dt in summary:
        print(f"{n:>5}{q:>3}{k:>4}{_fmt(c):>14}{a:>8}{d:>7}{dt:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
