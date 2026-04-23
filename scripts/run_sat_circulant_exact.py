#!/usr/bin/env python3
"""
scripts/run_sat_circulant_exact.py
==================================
Sweep driver for `SATCirculantExact` — the provably-optimal K4-free
circulant search via explicit MIS-subset encoding.

Per N, emits one graph under source='sat_circulant_exact' with metadata
  {connection_set, degree, alpha, proven, n_boxes_tried, status_counts}
where `proven=True` iff no box timed out (all returned INFEASIBLE or
OPTIMAL). See search/sat_circulant_exact.py for the encoding.

Run from repo root::

    micromamba run -n k4free python scripts/run_sat_circulant_exact.py \\
        --n-min 10 --n-max 40 --time-limit 60 --save
"""

import argparse
import csv
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, SATCirculantExact


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n-min", type=int, default=10)
    p.add_argument("--n-max", type=int, default=40)
    p.add_argument("--d-min", type=int, default=3)
    p.add_argument("--d-max", type=int, default=None)
    p.add_argument("--time-limit", type=float, default=60.0,
                   help="per-box SAT budget")
    p.add_argument("--alpha-time-limit", type=float, default=60.0)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--best-c-init", type=float, default=1.0,
                   help="skip boxes with c_log >= this initial bound")
    p.add_argument("--save", action="store_true",
                   help="persist to graph_db as source='sat_circulant_exact'")
    p.add_argument("--verbosity", type=int, default=1)
    p.add_argument("--logfile", default=None,
                   help="optional CSV of per-box status rows from verbose logs")
    args = p.parse_args()

    summary: list[tuple[int, float | None, int, int, int, float, bool, dict]] = []

    with AggregateLogger(name="sat_circulant_exact_sweep") as agg:
        for n in range(args.n_min, args.n_max + 1):
            t0 = time.monotonic()
            search = SATCirculantExact(
                n=n,
                top_k=1,
                verbosity=args.verbosity,
                parent_logger=agg,
                d_min=args.d_min,
                d_max=args.d_max,
                time_limit_per_box=args.time_limit,
                alpha_time_limit=args.alpha_time_limit,
                workers=args.workers,
                best_c_init=args.best_c_init,
            )
            results = search.run()
            if args.save:
                search.save(results)
            dt = time.monotonic() - t0
            if results:
                r = results[0]
                md = r.metadata or {}
                summary.append((
                    n, r.c_log, r.alpha, r.d_max,
                    md.get("n_boxes_tried", 0),
                    dt,
                    md.get("proven", False),
                    md.get("status_counts", {}),
                ))
                tag = "proven" if md.get("proven") else "partial"
                print(
                    f"[sat_circulant_exact n={n:>3}] {tag} "
                    f"c={_fmt(r.c_log)} α={r.alpha} d={r.d_max} "
                    f"S={md.get('connection_set')} "
                    f"boxes={md.get('n_boxes_tried')} "
                    f"status={md.get('status_counts')} "
                    f"({dt:.1f}s)",
                    flush=True,
                )
            else:
                summary.append((n, None, 0, 0, 0, dt, False, {}))
                print(f"[sat_circulant_exact n={n:>3}] no result ({dt:.1f}s)",
                      flush=True)

    print()
    print("=" * 90)
    print(f"{'n':>4}{'proven':>8}{'best c':>12}{'α':>4}{'d':>4}{'boxes':>7}"
          f"{'t(s)':>10}  status_counts")
    print("=" * 90)
    for n, c, a, d, nb, dt, proven, sc in summary:
        print(f"{n:>4}{str(proven):>8}{_fmt(c):>12}{a:>4}{d:>4}{nb:>7}"
              f"{dt:>10.2f}  {sc}")

    if args.logfile:
        os.makedirs(os.path.dirname(args.logfile) or ".", exist_ok=True)
        with open(args.logfile, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["n", "proven", "best_c", "alpha", "d_max",
                        "boxes", "time_s", "status_counts"])
            for n, c, a, d, nb, dt, proven, sc in summary:
                w.writerow([n, proven, c, a, d, nb, round(dt, 2), sc])
        print(f"\nwrote {args.logfile}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
