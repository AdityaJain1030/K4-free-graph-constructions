#!/usr/bin/env python3
"""
scripts/diag_sat_exact.py
===========================
Per-box diagnostic for SATExact. For each (α, d) pair in the scan
range, records status (FEASIBLE / INFEASIBLE / TIMEOUT /
INFEASIBLE_RAMSEY) and wallclock. The goal is not to find best
c_log — it is to see where the solver *gets stuck*, so we can attack
those specific boxes.

Usage::

    python -m scripts.diag_sat_exact --n 16 --timeout 30
    python -m scripts.diag_sat_exact --n-min 14 --n-max 18 --timeout 30
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search.sat_exact import SATExact
from utils.ramsey import degree_bounds


def _diag_one_n(n: int, timeout: float, workers: int,
                 symmetry_mode: str, ramsey_prune: bool,
                 alpha_range: range | None,
                 d_range: range | None) -> list[dict]:
    if alpha_range is None:
        alpha_range = range(1, n)
    rows = []
    for a in alpha_range:
        d_lo, d_hi = degree_bounds(n, a)
        loop_d = d_range if d_range is not None else range(1, n)
        for d in loop_d:
            s = SATExact(
                n=n, top_k=1, verbosity=0,
                alpha=a, d_max=d,
                timeout_s=timeout, workers=workers,
                symmetry_mode=symmetry_mode,
                ramsey_prune=ramsey_prune,
                scan_from_ramsey_floor=False,
            )
            t0 = time.monotonic()
            results = s.run()
            elapsed = time.monotonic() - t0
            if results:
                # FEASIBLE: returned a graph
                r = results[0]
                status = r.metadata.get("status", "FEASIBLE")
                c_log = r.c_log
            else:
                # Base class returned nothing — infer status from the
                # SATExact decision (Ramsey or solver INFEASIBLE/TIMEOUT).
                if ramsey_prune:
                    # Replicate the Ramsey-infeasible check.
                    if d_lo >= 0 and d_hi >= 0 and d_lo > d_hi:
                        status = "INFEASIBLE_RAMSEY"
                        elapsed = 0.0
                    elif d_lo >= 0 and d < d_lo:
                        status = "INFEASIBLE_RAMSEY"
                        elapsed = 0.0
                    else:
                        status = "INFEASIBLE_or_TIMEOUT"
                else:
                    status = "INFEASIBLE_or_TIMEOUT"
                c_log = None
            rows.append({
                "n":      n,
                "alpha":  a,
                "d_max":  d,
                "d_lo_R": d_lo, "d_hi_R": d_hi,
                "status": status,
                "c_log":  c_log,
                "t":      round(elapsed, 3),
            })
            mark = {
                "FEASIBLE": "✓F",
                "INFEASIBLE_RAMSEY": "·R",
                "INFEASIBLE_or_TIMEOUT": "··",
            }.get(status, status)
            print(f"  n={n:>2}  α={a:>2} d={d:>2}  "
                  f"[R-range {d_lo:>2}..{d_hi:>2}]  "
                  f"{mark}  c={c_log if c_log is None else round(c_log, 4)}  "
                  f"{elapsed:>7.2f}s", flush=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--n-min", type=int, default=None)
    ap.add_argument("--n-max", type=int, default=None)
    ap.add_argument("--alpha", type=int, default=None)
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--symmetry-mode", type=str, default="edge_lex")
    ap.add_argument("--no-ramsey", action="store_true")
    ap.add_argument("--out-json", type=str,
                    default=os.path.join(REPO, "logs",
                                         "sat_exact_diag.json"))
    args = ap.parse_args()

    if args.n is None and args.n_min is None:
        ap.error("Provide --n or --n-min/--n-max.")
    ns = ([args.n] if args.n is not None
          else list(range(args.n_min, (args.n_max or args.n_min) + 1)))
    alpha_range = range(args.alpha, args.alpha + 1) if args.alpha else None

    all_rows: list[dict] = []
    for n in ns:
        print(f"\n══ n={n}  timeout={args.timeout}s  sym={args.symmetry_mode}  "
              f"ramsey={not args.no_ramsey} ══", flush=True)
        rows = _diag_one_n(
            n=n,
            timeout=args.timeout,
            workers=args.workers,
            symmetry_mode=args.symmetry_mode,
            ramsey_prune=not args.no_ramsey,
            alpha_range=alpha_range,
            d_range=None,
        )
        all_rows.extend(rows)

    os.makedirs(os.path.dirname(os.path.abspath(args.out_json)) or ".",
                exist_ok=True)
    with open(args.out_json, "w") as f:
        json.dump(all_rows, f, indent=2)
    print(f"\nWrote per-box diag → {args.out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
