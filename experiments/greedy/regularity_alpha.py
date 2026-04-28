#!/usr/bin/env python3
"""
experiments/greedy/regularity_alpha.py
=======================================
Greedy regularity (`−(d_u + d_v)`) with a periodic α-stagnation
intervention. Built on `EdgeFlipWalk`.

The walk normally scores adds by `−(d_u + d_v)` like
`regularity.py`. Every `--alpha-check-every` accepted moves it
samples a greedy α lower bound (`alpha_lb`); if that bound has not
strictly decreased over the last `--stagnation-window` α-samples,
the next step's score switches to `−alpha_lb_post-add` (with the
degree score as a small tiebreaker). After one intervention step
the walk reverts to regularity scoring.

This is the port of the deleted `RegularityAlphaSearch` class.

Usage
-----
    python experiments/greedy/regularity_alpha.py --n 30
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
from utils.alpha_surrogate import alpha_lb

from random_capped import _DEFAULT_CAPS, make_capped_proposer  # type: ignore


_TIEBREAK = 0.05  # secondary signal — α-LB integer step (1.0) still dominates


def make_alpha_aware_scorer(
    alpha_check_every: int = 10,
    stagnation_window: int = 3,
    lb_restarts: int = 4,
):
    """
    Closure-state scorer.

    Most steps:           score = −(d_u + d_v)  (regularity)
    On stagnation:        score = −alpha_lb(post-add) − tie · (d_u + d_v)
                          (one intervention step, then revert)

    Stagnation = α has not strictly decreased over the last
    `stagnation_window` α samples.
    """
    state = {"history": [], "intervene_next": False}

    def scorer(adj: np.ndarray, moves: list, info: dict) -> np.ndarray:
        steps = int(info.get("steps", 0))
        deg = adj.sum(axis=1).astype(np.float64)
        rng = np.random.default_rng(steps)
        out = np.empty(len(moves), dtype=np.float64)

        # Periodic α probe: update history, decide whether next step intervenes.
        if steps > 0 and steps % alpha_check_every == 0:
            current = float(alpha_lb(adj, restarts=lb_restarts, rng=rng))
            history = state["history"]
            history.append(current)
            del history[: max(0, len(history) - stagnation_window - 1)]
            if len(history) >= stagnation_window + 1:
                older = history[: -stagnation_window]
                recent = history[-stagnation_window:]
                state["intervene_next"] = min(recent) >= max(older)

        if state["intervene_next"]:
            # One-step α-targeting fallback
            work = adj.copy()
            for i, (u, v, _is_add) in enumerate(moves):
                work[u, v] = work[v, u] = 1
                a = float(alpha_lb(work, restarts=lb_restarts, rng=rng))
                out[i] = -a - _TIEBREAK * (deg[u] + deg[v])
                work[u, v] = work[v, u] = 0
            state["intervene_next"] = False
        else:
            for i, (u, v, _is_add) in enumerate(moves):
                out[i] = -(deg[u] + deg[v])
        return out

    return scorer


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def run(args) -> None:
    caps_raw = [int(c) for c in args.caps.split(",") if c.strip()]
    caps = sorted({c for c in caps_raw if 1 <= c <= args.n - 1})

    print(f"\n  greedy/regularity_alpha — port of RegularityAlphaSearch via EdgeFlipWalk")
    print(
        f"  base score = −(d_u + d_v),  β=∞,  α-stagnation intervention "
        f"(check every {args.alpha_check_every}, window {args.stagnation_window})"
    )
    print(f"  n={args.n}  caps={caps}  trials={args.trials}  seed={args.seed}")
    print("  " + "-" * 72)

    overall_best = None
    overall_best_cap = None

    with AggregateLogger(name="greedy_regularity_alpha") as agg:
        for d_cap in caps:
            search = EdgeFlipWalk(
                n=args.n,
                stop_fn=None,
                propose_from_valid_moves_fn=make_capped_proposer(d_cap),
                batch_score_fn=make_alpha_aware_scorer(
                    alpha_check_every=args.alpha_check_every,
                    stagnation_window=args.stagnation_window,
                ),
                beta=float("inf"),
                top_k=args.trials,
                verbosity=0,
                parent_logger=agg,
                num_trials=args.trials,
                seed=args.seed,
                max_steps=10 * args.n * args.n,
                max_consecutive_failures=1,
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
            if args.save and best.is_k4_free:
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
    ap.add_argument("--alpha-check-every", type=int, default=10,
                    help="probe greedy α every K accepted steps")
    ap.add_argument("--stagnation-window", type=int, default=3,
                    help="how many consecutive non-decreases before intervening")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
