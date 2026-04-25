#!/usr/bin/env python3
"""
scripts/run_sat_near_regular_nonreg.py
=======================================
Grid runner for SATNearRegularNonReg — enumerates non-regular,
near-regular K4-free graphs at targeted (n, α) pairs and saves to
graph_db under source="sat_near_regular_nonreg".

For each n in the grid, the α targets are drawn from the current
graph_db frontier (per-n minimum-c_log row). You can optionally
supplement with α ± 1 to explore neighbouring points where a non-VT
near-regular construction might dominate a Cayley one.

Run from repo root::

    micromamba run -n k4free python scripts/run_sat_near_regular_nonreg.py
    micromamba run -n k4free python scripts/run_sat_near_regular_nonreg.py \
        --n-range 14-28 --alpha-neighbourhood 1 --per-case-timeout 180 \
        --max-iso 15
"""

from __future__ import annotations

import argparse
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB
from search import AggregateLogger, SATNearRegularNonReg
from utils.nauty import canonical_id


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def _frontier_alphas(db: DB, n_range) -> dict[int, list[int]]:
    """
    For each n in n_range, return the alpha value of the current
    best-c_log row in graph_db (the frontier α).
    """
    out: dict[int, list[int]] = {}
    for r in db.frontier(by='n', minimize='c_log'):
        if r['n'] in n_range and r.get('alpha') is not None:
            out[r['n']] = [int(r['alpha'])]
    return out


def _expand_neighbours(alphas: dict[int, list[int]], radius: int, n_range):
    out: dict[int, list[int]] = {}
    for n in n_range:
        base = alphas.get(n, [])
        if not base:
            continue
        vals = set()
        for a in base:
            for delta in range(-radius, radius + 1):
                v = a + delta
                if 1 <= v < n:
                    vals.add(v)
        out[n] = sorted(vals)
    return out


def _best_c_log_for_n(db: DB, n: int) -> float | None:
    # c_log can be None for degenerate rows; exclude with an open-upper range.
    rows = db.query(where={'n': n}, ranges={'c_log': (0.0, None)},
                    order_by='c_log', limit=1)
    return rows[0]['c_log'] if rows else None


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--n-range", default="14-26",
                   help="inclusive n range, e.g. 14-26")
    p.add_argument("--alpha-neighbourhood", type=int, default=0,
                   help="expand each frontier α by ±k (default 0 = only frontier α)")
    p.add_argument("--alpha-override", default=None,
                   help="comma-separated n=alpha overrides, e.g. '14=3,15=3,23=6'")
    p.add_argument("--per-case-timeout", type=float, default=180.0,
                   help="wall cap per (n, α) case")
    p.add_argument("--per-D-timeout", type=float, default=120.0,
                   help="wall cap per D within a case")
    p.add_argument("--max-iso", type=int, default=15,
                   help="max unique iso classes per D")
    p.add_argument("--max-labeled", type=int, default=200,
                   help="max labeled solver iters per D (iso orbit guard)")
    p.add_argument("--scan-mode", default="first",
                   choices=["first", "all", "k_after_first"])
    p.add_argument("--scan-extra-D", type=int, default=0)
    p.add_argument("--symmetry-mode", default="chain",
                   choices=["none", "chain", "edge_lex", "chain+edge_lex"])
    p.add_argument("--workers", type=int, default=None)
    p.add_argument("--dry-run", action="store_true",
                   help="print the grid, do nothing else")
    p.add_argument("--no-save", action="store_true",
                   help="run but don't write to graph_db")
    args = p.parse_args()

    lo, hi = [int(x) for x in args.n_range.split("-")]
    n_range = list(range(lo, hi + 1))

    overrides: dict[int, list[int]] = {}
    if args.alpha_override:
        for tok in args.alpha_override.split(","):
            k, v = tok.split("=")
            overrides.setdefault(int(k), []).append(int(v))

    with DB(auto_sync=False) as db:
        frontier_alpha = _frontier_alphas(db, n_range)
        grid = _expand_neighbours(frontier_alpha, args.alpha_neighbourhood, n_range)
        for n, alphas in overrides.items():
            grid[n] = sorted(set(grid.get(n, []) + alphas))
        # Snapshot each n's best c_log for a delta report.
        best_pre = {n: _best_c_log_for_n(db, n) for n in n_range}

    print(f"Grid ({len(grid)} n-values):")
    for n in sorted(grid):
        print(f"  n={n:3d}  α ∈ {grid[n]}  best_c_log_in_db={_fmt(best_pre[n])}")
    if args.dry_run:
        return 0

    summary: list[dict] = []

    with AggregateLogger(name="sat_near_regular_nonreg_sweep") as agg:
        for n in sorted(grid):
            for a in grid[n]:
                t0 = time.monotonic()
                s = SATNearRegularNonReg(
                    n=n, alpha=a,
                    timeout_s=args.per_case_timeout,
                    per_D_timeout_s=args.per_D_timeout,
                    max_iso_per_D=args.max_iso,
                    max_labeled_per_D=args.max_labeled,
                    scan_mode=args.scan_mode,
                    scan_extra_D=args.scan_extra_D,
                    symmetry_mode=args.symmetry_mode,
                    workers=args.workers,
                    verbosity=1,
                    top_k=args.max_iso * max(1, 1 + args.scan_extra_D),
                    parent_logger=agg,
                )
                results = s.run()
                dt = time.monotonic() - t0

                ids_written = []
                if results and not args.no_save:
                    ids_written = s.save(results)

                best_c = min((r.c_log for r in results if r.c_log is not None),
                             default=None)
                iso_ids = sorted({r.metadata.get("iso_canonical_id", "")
                                  for r in results})
                summary.append({
                    "n": n, "alpha": a,
                    "n_iso": len(iso_ids),
                    "best_c_log": best_c,
                    "elapsed_s": dt,
                    "ids_written": ids_written,
                })
                print(f"[n={n:3d} α={a:2d}] iso={len(iso_ids):3d}  "
                      f"best_c_log={_fmt(best_c)}  "
                      f"({dt:.1f}s)  saved={len([x for x in ids_written if x[1]])}/{len(ids_written)} new")

    # Post-sweep: compare best_c_log found against pre-sweep frontier.
    print()
    print("=" * 80)
    print(f"{'n':>4}{'α':>4}{'iso':>5}{'best c_log':>14}"
          f"{'frontier c_log':>18}{'Δ vs frontier':>16}")
    print("=" * 80)
    for row in summary:
        n = row["n"]
        pre = best_pre.get(n)
        c = row["best_c_log"]
        delta = (c - pre) if (c is not None and pre is not None) else None
        print(f"{n:>4}{row['alpha']:>4}{row['n_iso']:>5}"
              f"{_fmt(c):>14}{_fmt(pre):>18}"
              f"{('—' if delta is None else f'{delta:+.4f}'):>16}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
