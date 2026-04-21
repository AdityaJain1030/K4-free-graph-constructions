#!/usr/bin/env python3
"""
scripts/run_cayley_tabu.py
===========================
Drive `CayleyTabuSearch` across a range of N and persist results to
graph_db under source='cayley_tabu'. The db is the single source of
truth; --better-only incrementality reads the existing best-per-N from
it.

For each N ∈ [--n-lo, --n-hi] (or --n-list), runs tabu over every
supported group of order N (cyclic, dihedral, direct products,
ℤ_3 × ℤ_2^k, ℤ_2^k). Surrogate α during search, exact α for the
final score. Keeps top-k per N across all groups.

Run::

    micromamba run -n k4free python scripts/run_cayley_tabu.py \\
        --n-lo 10 --n-hi 30 --n-iters 300 --n-restarts 3 \\
        --time-limit 60 --top-k 3
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS
from search import AggregateLogger, CayleyTabuSearch


def _fmt(x):
    return "—" if x is None else f"{x:.6f}"


def _best_c_per_n_from_db(store: GraphStore, source: str = "cayley_tabu") -> dict[int, float]:
    """Read the current best c_log per N from db records of the given source."""
    best: dict[int, float] = {}
    for r in store.all_records():
        if r.get("source") != source:
            continue
        md = r.get("metadata", {})
        n = md.get("n")
        c = md.get("c_log")
        if n is None or c is None:
            continue
        if n not in best or c < best[n]:
            best[n] = float(c)
    return best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-lo", type=int, default=10)
    ap.add_argument("--n-hi", type=int, default=40)
    ap.add_argument("--n-list", type=int, nargs="*", default=None,
                    help="Explicit list of N values. Overrides --n-lo/--n-hi.")
    ap.add_argument("--better-only", action="store_true",
                    help="Skip N's where the db already has a c_log ≤ what this run "
                         "finds. Reads existing bests from graph_db (source='cayley_tabu').")
    ap.add_argument("--n-iters", type=int, default=300)
    ap.add_argument("--n-restarts", type=int, default=3)
    ap.add_argument("--lb-restarts", type=int, default=24)
    ap.add_argument("--tabu-len", type=int, default=None)
    ap.add_argument("--time-limit", type=float, default=90.0,
                    help="Wall-clock cap per group (seconds).")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--random-seed", type=int, default=20260421)
    ap.add_argument("--no-save-db", action="store_true",
                    help="Don't persist to graph_db. Default is to save.")
    ap.add_argument("--groups", nargs="*", default=None,
                    help="Restrict to these group names (default: all).")
    ap.add_argument("--verbosity", type=int, default=1)
    args = ap.parse_args()

    save_db = not args.no_save_db
    store = GraphStore(DEFAULT_GRAPHS) if (save_db or args.better_only) else None
    existing_best: dict[int, float] = (
        _best_c_per_n_from_db(store) if (store and args.better_only) else {}
    )

    if args.n_list:
        n_values = sorted(set(args.n_list))
    else:
        n_values = list(range(args.n_lo, args.n_hi + 1))

    with AggregateLogger(name="cayley_tabu_sweep") as agg:
        for n in n_values:
            t0 = time.monotonic()
            s = CayleyTabuSearch(
                n=n,
                top_k=args.top_k,
                verbosity=args.verbosity,
                parent_logger=agg,
                n_iters=args.n_iters,
                n_restarts=args.n_restarts,
                lb_restarts=args.lb_restarts,
                tabu_len=args.tabu_len,
                time_limit_s=args.time_limit,
                groups=args.groups,
                random_seed=args.random_seed + n,
            )
            results = s.run()
            dt = time.monotonic() - t0

            best = results[0] if results else None
            new_c = best.c_log if best else None
            prev_c = existing_best.get(n)

            # --better-only: skip persistence when existing is <= new.
            keep_prev = (
                args.better_only
                and prev_c is not None
                and (new_c is None or new_c >= prev_c - 1e-9)
            )

            note = ""
            if save_db and results and not keep_prev:
                s.save(results)
                if prev_c is not None and new_c is not None and new_c < prev_c - 1e-9:
                    note = "(improved)"
            elif keep_prev:
                note = "(kept prev)"

            if best:
                print(
                    f"[N={n:>3}] best c={_fmt(new_c)}  "
                    f"α={best.alpha}  d={best.d_max}  "
                    f"group={best.metadata.get('group') or '—':<10}  "
                    f"({dt:.1f}s) {note}",
                    flush=True,
                )
            else:
                print(
                    f"[N={n:>3}] best c=—  α=None  d=None  "
                    f"group=—           ({dt:.1f}s) {note}",
                    flush=True,
                )

    print("\nDone.")
    if save_db:
        print("Persisted to graph_db under source='cayley_tabu'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
