#!/usr/bin/env python3
"""
experiments/random/add_remove_edges.py
=======================================
Uniform random walk over the FULL valid moveset (adds + removes) on
K4-free graphs. No scoring — every legal move is equally likely. The
walk halts on a caller-supplied stop rule.

Why this exists: the structured `add_remove_edges_weighted.py` shows
that exposing removes pays off only when the score is sharp enough to
direct them. This script is the unscored baseline — what does the
walk find when removes are *unbiased* and the stop rule does all the
work?

Stop modes:
  --stop edges   --target T   stop when |E| >= T (rarely interesting,
                              walk thrashes around the target)
  --stop d_max   --target T   stop when max degree >= T
  --stop alpha   --target T   stop when α(G) <= T   (CP-SAT, every 5 steps)

`--stop alpha` is the headline configuration: at each α probe the walk
has had a chance to remove edges that previously bumped α up, so the
α target can be hit at lower d_max than an add-only walk would give.

Usage
-----
    python experiments/random/add_remove_edges.py --n 20 --stop alpha --target 5
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

from add_edges import STOP_BUILDERS  # type: ignore


def propose_adds_and_removes(adj, valid_moves, info, rng, k):
    """Identity proposer: expose every legal move (adds + removes) to the
    walk's uniform sampler."""
    if not valid_moves:
        return []
    if k is None or k >= len(valid_moves):
        return valid_moves
    idx = rng.choice(len(valid_moves), size=k, replace=False)
    return [valid_moves[i] for i in idx]


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def run(n: int, stop: str, target, num_trials: int, seed: int,
        n_candidates: int | None, do_save: bool) -> None:
    stop_fn = STOP_BUILDERS[stop](int(target))

    with AggregateLogger(name="add_remove_edges") as agg:
        search = EdgeFlipWalk(
            n=n,
            stop_fn=stop_fn,
            propose_from_valid_moves_fn=propose_adds_and_removes,
            top_k=1,
            verbosity=0,
            parent_logger=agg,
            num_trials=num_trials,
            seed=seed,
            n_candidates=n_candidates,
            max_steps=50 * n * n,
            max_consecutive_failures=5 * n * n,
        )
        results = search.run()
        if do_save and results:
            search.save([r for r in results if r.is_k4_free])

    if not results:
        print(f"[n={n}] no result")
        return

    print(f"\n  add_remove_edges  n={n}  stop={stop}  target={target}  "
          f"trials={num_trials}")
    print("  " + "-" * 70)
    for i, r in enumerate(results):
        added = r.metadata.get("added", 0)
        removed = r.metadata.get("removed", 0)
        print(f"  trial {i:>2}: c_log={_fmt(r.c_log)}  α={r.alpha:>3}  "
              f"d_max={r.d_max:>3}  |E|={r.metadata.get('edges', 0):>4}  "
              f"+{added}/-{removed}")
    best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
    print(f"  best c_log = {_fmt(best.c_log)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True, help="vertex count")
    ap.add_argument("--stop", choices=list(STOP_BUILDERS), required=True)
    ap.add_argument("--target", required=True,
                    help="target value for the chosen stop criterion (int)")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--n-cands", type=int, default=None)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    run(args.n, args.stop, int(args.target), args.trials, args.seed,
        args.n_cands, args.save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
