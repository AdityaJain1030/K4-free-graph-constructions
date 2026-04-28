#!/usr/bin/env python3
"""
experiments/greedy/regularity.py
=================================
Greedy degree-variance minimisation. Built on `EdgeFlipWalk`.

Score every K4-safe add by `−(d_u + d_v)` and pick the argmax (β=∞).
Equivalent to "minimise post-add variance of the degree sequence" up
to a monotone transform: lowest combined endpoint degree ↔ smallest
variance bump. Same `d_cap` sweep as `random_capped.py`.

This is the port of the deleted `RegularitySearch` class.
`add_edges_weighted.py --weight d_min` is the same scorer with
soft β instead of greedy argmax.

Usage
-----
    python experiments/greedy/regularity.py --n 30
    python experiments/greedy/regularity.py --n 30 --caps 5,7,10
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

from random_capped import _DEFAULT_CAPS, make_capped_proposer  # type: ignore


def score_neg_d_sum(adj: np.ndarray, moves: list, info: dict) -> np.ndarray:
    """Higher score = lower combined endpoint degree."""
    deg = adj.sum(axis=1).astype(np.float64)
    out = np.empty(len(moves), dtype=np.float64)
    for i, (u, v, _is_add) in enumerate(moves):
        out[i] = -(deg[u] + deg[v])
    return out


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def run(n: int, caps: list[int], num_trials: int, seed: int, do_save: bool) -> None:
    print(f"\n  greedy/regularity — port of RegularitySearch via EdgeFlipWalk")
    print(f"  score = −(d_u + d_v),  β=∞ (greedy argmax),  saturation halt")
    print(f"  n={n}  caps={caps}  trials={num_trials}  seed={seed}")
    print("  " + "-" * 72)

    overall_best = None
    overall_best_cap = None

    with AggregateLogger(name="greedy_regularity") as agg:
        for d_cap in caps:
            search = EdgeFlipWalk(
                n=n,
                stop_fn=None,
                propose_from_valid_moves_fn=make_capped_proposer(d_cap),
                batch_score_fn=score_neg_d_sum,
                beta=float("inf"),                 # greedy argmax
                top_k=num_trials,
                verbosity=0,
                parent_logger=agg,
                num_trials=num_trials,
                seed=seed,
                max_steps=10 * n * n,
                max_consecutive_failures=1,        # cap-saturation = halt
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
