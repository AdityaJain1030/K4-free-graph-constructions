#!/usr/bin/env python3
"""
experiments/brute_force/run_brute_force.py
==========================================
Exhaustive K4-free ground-truth enumeration via nauty ``geng``.

Streams every non-isomorphic K4-free graph on n vertices, scores each by
c_log, persists the best per N to graph_db (filename=brute_force.json),
and prints a markdown summary table. Feasible up to n=10.

Run from repo root::

    micromamba run -n k4free python experiments/brute_force/run_brute_force.py
    micromamba run -n k4free python experiments/brute_force/run_brute_force.py --n-min 3 --n-max 10
    micromamba run -n k4free python experiments/brute_force/run_brute_force.py --n 8
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO))

from search import AggregateLogger, BruteForce


def _fmt(x: float | None) -> str:
    return "—" if x is None else f"{x:.4f}"


def run_n(n: int, *, top_k: int, save: bool, verbosity: int, agg) -> dict | None:
    t0 = time.monotonic()
    search = BruteForce(n=n, top_k=top_k, verbosity=verbosity, parent_logger=agg)
    results = search.run()
    dt = time.monotonic() - t0

    if not results:
        print(f"[brute_force n={n:>3}] 0 results — geng unavailable or n too small ({dt:.2f}s)")
        return None

    best = results[0]
    G = best.G
    degs = [d for _, d in G.degree()]
    d_min = min(degs) if degs else 0
    n_edges = G.number_of_edges()
    regular = (d_min == best.d_max)

    print(
        f"[brute_force n={n:>3}] {len(results):>5} kept  "
        f"best c_log={_fmt(best.c_log)}  α={best.alpha}  d_max={best.d_max}  "
        f"|E|={n_edges}  regular={'Y' if regular else 'N'}  ({dt:.2f}s)"
    )

    if save:
        search.save([results[0]])

    return {
        "n": n,
        "c_log": best.c_log,
        "alpha": best.alpha,
        "d_max": best.d_max,
        "d_min": d_min,
        "edges": n_edges,
        "regular": regular,
        "elapsed_s": dt,
    }


def print_table(rows: list[dict]) -> None:
    print()
    print("## Optimal K₄-free graphs by N (brute force)")
    print()
    print("| N | best c_log | α | d_max | d_min | \\|E\\| | regular |")
    print("|---|---|---|---|---|---|---|")
    for r in rows:
        print(
            f"| {r['n']} | {_fmt(r['c_log'])} | {r['alpha']} | "
            f"{r['d_max']} | {r['d_min']} | {r['edges']} | "
            f"{'✓' if r['regular'] else '·'} |"
        )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    group = p.add_mutually_exclusive_group()
    group.add_argument("--n", type=int, help="Single n to run.")
    group.add_argument("--n-min", type=int, default=3)
    p.add_argument("--n-max", type=int, default=10)
    p.add_argument("--top-k", type=int, default=1,
                   help="Keep top-k by c_log (default 1).")
    p.add_argument("--no-save", action="store_true",
                   help="Skip persisting the best graph per N to graph_db.")
    p.add_argument("--verbosity", type=int, default=1)
    args = p.parse_args()

    ns = [args.n] if args.n is not None else list(range(args.n_min, args.n_max + 1))

    rows: list[dict] = []
    with AggregateLogger(name="brute_force_sweep") as agg:
        for n in ns:
            row = run_n(
                n,
                top_k=args.top_k,
                save=not args.no_save,
                verbosity=args.verbosity,
                agg=agg,
            )
            if row is not None:
                rows.append(row)

    if rows:
        print_table(rows)

    return 0


if __name__ == "__main__":
    sys.exit(main())
