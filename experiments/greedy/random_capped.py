#!/usr/bin/env python3
"""
experiments/greedy/random_capped.py
====================================
Degree-capped random K4-free edge addition. Built on `EdgeFlipWalk`.

For each `d_cap` in a sweep, run `num_trials` independent walks that
add uniformly random K4-safe edges with the constraint that both
endpoints have degree below `d_cap`. The walk halts when no such
edge remains (cap-saturation). Best per (cap, trial) is reported.

This is the port of the deleted `RandomSearch` class. Same policy
(uniform add-only with degree cap, two-pass shuffled-greedy build),
new engine (EdgeFlipWalk).

Usage
-----
    python experiments/greedy/random_capped.py --n 30
    python experiments/greedy/random_capped.py --n 30 --caps 5,7,10 --trials 5
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk


_DEFAULT_CAPS = (3, 4, 5, 6, 8, 10, 12, 15, 20)


def make_capped_proposer(d_cap: int):
    """Return a proposer that exposes only add moves where both endpoints
    have degree < d_cap. When no such add exists, returns [] → walk halts."""
    def propose(adj, valid_moves, info, rng, k):
        deg = adj.sum(axis=1)
        adds = [m for m in valid_moves
                if m[2] and deg[m[0]] < d_cap and deg[m[1]] < d_cap]
        if not adds:
            return []
        if k is None or k >= len(adds):
            return adds
        idx = rng.choice(len(adds), size=k, replace=False)
        return [adds[i] for i in idx]
    return propose


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def run(n: int, caps: list[int], num_trials: int, seed: int, do_save: bool) -> None:
    print(f"\n  greedy/random_capped — port of RandomSearch via EdgeFlipWalk")
    print(f"  n={n}  caps={caps}  trials={num_trials}  seed={seed}")
    print("  " + "-" * 72)

    overall_best = None
    overall_best_cap = None

    with AggregateLogger(name="greedy_random_capped") as agg:
        for d_cap in caps:
            search = EdgeFlipWalk(
                n=n,
                stop_fn=None,
                propose_from_valid_moves_fn=make_capped_proposer(d_cap),
                top_k=num_trials,
                verbosity=0,
                parent_logger=agg,
                num_trials=num_trials,
                seed=seed,
                max_steps=10 * n * n,
                max_consecutive_failures=1,  # cap-saturation = halt
            )
            results = search.run()
            if not results:
                print(f"  d_cap={d_cap:>2}  no result")
                continue
            best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
            print(
                f"  d_cap={d_cap:>2}  best c_log={_fmt(best.c_log)}  "
                f"α={best.alpha:>3}  d={best.d_max:>3}  "
                f"|E|={best.metadata.get('edges', 0):>4}"
            )
            if do_save and best.is_k4_free:
                search.save([best])
            if overall_best is None or (
                best.c_log is not None
                and (overall_best.c_log is None or best.c_log < overall_best.c_log)
            ):
                overall_best = best
                overall_best_cap = d_cap

    if overall_best is None:
        print("\n  no overall best found")
        return
    print(
        f"\n  overall best  d_cap={overall_best_cap}  "
        f"c_log={_fmt(overall_best.c_log)}  α={overall_best.alpha}  "
        f"d={overall_best.d_max}  |E|={overall_best.metadata.get('edges', 0)}"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--caps", default=",".join(str(c) for c in _DEFAULT_CAPS),
                    help="comma-separated list of degree caps")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    caps_raw = [int(c) for c in args.caps.split(",") if c.strip()]
    caps = sorted({c for c in caps_raw if 1 <= c <= args.n - 1})
    run(args.n, caps, args.trials, args.seed, args.save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
