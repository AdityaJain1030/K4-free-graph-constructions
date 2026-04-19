#!/usr/bin/env python3
"""
scripts/run_sat_exact.py
==========================
CLI driver for SATExact (search/sat_exact.py).

Examples::

    # Full scan for one N (scans α and d_max)
    python -m scripts.run_sat_exact --n 20

    # Scan d_max at a fixed α
    python -m scripts.run_sat_exact --n 25 --alpha 5

    # One box
    python -m scripts.run_sat_exact --n 18 --alpha 3 --d-max 6

    # Sweep across N=10..20
    python -m scripts.run_sat_exact --n-min 10 --n-max 20
"""

import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search import AggregateLogger, SATExact


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


# Per SAT_SIMPLE.md eval table.
def _default_timeout(n: int) -> float:
    if n <= 18:
        return 60.0
    if n <= 22:
        return 180.0
    return 300.0


def _run_one(n, alpha, d_max, timeout, workers, verbosity, parent_logger,
             top_k, save, parallel_alpha, parallel_alpha_tracks,
             circulant_hints, branch_on_v0):
    t0 = time.monotonic()
    search = SATExact(
        n=n,
        top_k=top_k,
        verbosity=verbosity,
        parent_logger=parent_logger,
        alpha=alpha,
        d_max=d_max,
        timeout_s=timeout,
        workers=workers,
        parallel_alpha=parallel_alpha,
        parallel_alpha_tracks=parallel_alpha_tracks,
        circulant_hints=circulant_hints,
        branch_on_v0=branch_on_v0,
    )
    results = search.run()
    if save and results:
        search.save(results)
    dt = time.monotonic() - t0
    return results, dt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None, help="Single N to run.")
    ap.add_argument("--n-min", type=int, default=None)
    ap.add_argument("--n-max", type=int, default=None)
    ap.add_argument("--alpha", type=int, default=None)
    ap.add_argument("--d-max", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=None,
                    help="Per-box SAT timeout in seconds. "
                         "Default: 60 (N≤18), 180 (19-22), 300 (>22).")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--top-k", type=int, default=1)
    ap.add_argument("--verbosity", type=int, default=1)
    ap.add_argument("--save", action="store_true",
                    help="Persist results to graph_db.")
    ap.add_argument("--parallel-alpha", action="store_true",
                    help="Dispatch α-tracks to worker processes. "
                         "Server-only: each track holds its own CP-SAT "
                         "model, so memory scales with the number of "
                         "α values. Do not enable on the laptop.")
    ap.add_argument("--parallel-alpha-tracks", type=int, default=0,
                    help="Worker count for --parallel-alpha. "
                         "0 → one track per α.")
    ap.add_argument("--circulant-hints", action="store_true",
                    help="Pass the best K4-free circulant for this n "
                         "(from CirculantSearchFast) as a CP-SAT "
                         "warm-start hint. Neutral-to-negative on "
                         "laptop benches; kept as opt-in for larger N "
                         "where FEASIBLE boxes dominate.")
    ap.add_argument("--branch-on-v0", action="store_true",
                    help="Add a FIXED_SEARCH decision strategy on the "
                         "vertex-0 row (CHOOSE_FIRST, SELECT_MAX_VALUE). "
                         "Only one portfolio worker uses it; rest stay "
                         "free. Complements edge_lex on row 0.")
    ap.add_argument("--out-json", type=str, default=None,
                    help="Write sweep summary to this JSON file.")
    args = ap.parse_args()

    if args.n is None and args.n_min is None:
        ap.error("Provide --n or --n-min/--n-max.")
    ns = (
        [args.n]
        if args.n is not None
        else list(range(args.n_min, (args.n_max or args.n_min) + 1))
    )

    summary: list[dict] = []
    with AggregateLogger(name="sat_exact_sweep") as agg:
        for n in ns:
            timeout = args.timeout if args.timeout is not None else _default_timeout(n)
            results, dt = _run_one(
                n=n,
                alpha=args.alpha,
                d_max=args.d_max,
                timeout=timeout,
                workers=args.workers,
                verbosity=args.verbosity,
                parent_logger=agg,
                top_k=args.top_k,
                save=args.save,
                parallel_alpha=args.parallel_alpha,
                parallel_alpha_tracks=args.parallel_alpha_tracks,
                circulant_hints=args.circulant_hints,
                branch_on_v0=args.branch_on_v0,
            )

            # Collect per-box statuses from the metadata of returned graphs.
            boxes = [r.metadata.get("status", "FEASIBLE") for r in results]
            timeouts = sum(1 for s in boxes if s == "TIMEOUT")

            if results:
                best = results[0]
                summary.append({
                    "n":          n,
                    "n_results":  len(results),
                    "best_c_log": best.c_log,
                    "best_alpha": best.alpha,
                    "best_dmax":  best.d_max,
                    "elapsed_s":  round(dt, 3),
                    "timeouts":   timeouts,
                    "per_box":    boxes,
                })
                print(
                    f"[sat_exact n={n:>2}] {len(results)} results, "
                    f"best c_log={_fmt(best.c_log)}  α={best.alpha}  "
                    f"d_max={best.d_max}  timeouts={timeouts}  ({dt:.2f}s)"
                )
            else:
                summary.append({
                    "n":          n,
                    "n_results":  0,
                    "best_c_log": None,
                    "best_alpha": None,
                    "best_dmax":  None,
                    "elapsed_s":  round(dt, 3),
                    "timeouts":   timeouts,
                    "per_box":    boxes,
                })
                print(
                    f"[sat_exact n={n:>2}] 0 results  timeouts={timeouts}  "
                    f"({dt:.2f}s)"
                )

    print()
    print("=" * 78)
    print(f"{'n':>4}{'k':>4}{'best c_log':>14}{'alpha':>8}{'d_max':>7}"
          f"{'TOs':>5}{'t (s)':>10}")
    print("=" * 78)
    for row in summary:
        print(
            f"{row['n']:>4}{row['n_results']:>4}"
            f"{_fmt(row['best_c_log']):>14}"
            f"{(row['best_alpha'] or 0):>8}{(row['best_dmax'] or 0):>7}"
            f"{row['timeouts']:>5}{row['elapsed_s']:>10.2f}"
        )

    if args.out_json:
        os.makedirs(os.path.dirname(os.path.abspath(args.out_json)) or ".",
                    exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(summary, f, indent=2)
        print(f"\nWrote summary → {args.out_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
