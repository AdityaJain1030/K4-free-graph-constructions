#!/usr/bin/env python3
"""
experiments/random/add_remove_edges_weighted.py
================================================
Same as add_edges_weighted.py but allows REMOVE moves too — the walk can
back out of bad adds. Built on EdgeFlipWalk with the full valid set
(adds + removes) exposed to the scorer + softmax.

Each weighting mode scores both move types coherently:

  target_regular  squared-distance to t = n^{2/3} on post-move degrees
                  (adds win below target; removes win above; empty graph
                  is not optimal because ℓ(0) = t² > 0)
  alpha   score = -alpha_lb on the post-move adjacency, for both add/remove.
  c_log   score = -c_log_surrogate on the post-move adjacency.

Without a stop_fn the walk runs until max_steps or stalls. The remove
moves let it escape saturation, so this never naturally halts at K4-
saturation like Bohman–Keevash does.

Usage
-----
    python experiments/random/add_remove_edges_weighted.py \
        --n 25 --weight c_log --stop edges --target 100 --beta 4
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk
from utils.alpha_surrogate import alpha_lb, c_log_surrogate

from add_edges_weighted import STOP_BUILDERS  # type: ignore


# ── batch scorers covering both add and remove ────────────────────────────

def score_target_regular(adj: np.ndarray, moves: list, info: dict) -> np.ndarray:
    """
    Regularity-toward-target score: prefer the move that pulls the degree
    sequence closer to a target value `t` (default n^{2/3}, the
    Bohman–Keevash typical degree).

    For each move flipping (u,v) by δ∈{+1,-1}, the per-vertex squared
    distance to target changes by
        Δloss = (d_u + δ - t)² + (d_v + δ - t)² − (d_u - t)² − (d_v - t)²
              = 2δ·(d_u + d_v) − 4δ·t + 2
    Score = −Δloss (higher = move is more improving). Adds beat removes when
    endpoints are below target; removes beat adds when endpoints are above.
    The empty graph is not a fixed point because ℓ(0) = t² > 0.
    """
    deg = adj.sum(axis=1).astype(np.float64)
    n = float(len(deg))
    t = max(2.0, n ** (2.0 / 3.0))
    out = np.empty(len(moves), dtype=np.float64)
    for i, (u, v, is_add) in enumerate(moves):
        delta = 1.0 if is_add else -1.0
        d_loss = 2.0 * delta * (deg[u] + deg[v]) - 4.0 * delta * t + 2.0
        out[i] = -d_loss
    return out


# Tiebreaker so degree breaks ties when the primary score (alpha_lb or
# c_log_surrogate) collides across candidates.
_TIEBREAK = 0.05  # secondary signal; α-LB integer step still dominates


def _score_post_move(adj: np.ndarray, moves: list, info: dict, fn) -> np.ndarray:
    rng = np.random.default_rng(int(info.get("steps", 0)))
    deg = adj.sum(axis=1).astype(np.float64)
    out = np.empty(len(moves), dtype=np.float64)
    work = adj.copy()
    for i, (u, v, is_add) in enumerate(moves):
        prev = work[u, v]
        work[u, v] = work[v, u] = 1 if is_add else 0
        val = fn(work, rng)
        primary = -val if np.isfinite(val) else -1e6
        # tiebreaker: low-degree adds preferred; high-degree removes preferred
        tie = -(deg[u] + deg[v]) if is_add else +(deg[u] + deg[v])
        out[i] = primary + _TIEBREAK * tie
        work[u, v] = work[v, u] = prev
    return out


def score_alpha(adj, moves, info):
    return _score_post_move(adj, moves, info,
                            lambda a, rng: float(alpha_lb(a, restarts=4, rng=rng)))


def score_c_log(adj, moves, info):
    return _score_post_move(adj, moves, info,
                            lambda a, rng: c_log_surrogate(a, lb_restarts=4, rng=rng))


SCORERS = {
    "target_regular": score_target_regular,
    "alpha": score_alpha,
    "c_log": score_c_log,
}


def propose_adds_and_removes(adj, valid_moves, info, rng, k):
    return valid_moves


def _fmt(x): return "—" if x is None else f"{x:.4f}"


def run(args) -> None:
    n = args.n
    stop_fn = None if args.stop == "none" else STOP_BUILDERS[args.stop](int(args.target))
    scorer = SCORERS[args.weight]

    with AggregateLogger(name=f"add_remove_weighted_{args.weight}") as agg:
        search = EdgeFlipWalk(
            n=n,
            stop_fn=stop_fn,
            propose_from_valid_moves_fn=propose_adds_and_removes,
            batch_score_fn=scorer,
            beta=args.beta,
            top_k=1,
            verbosity=0,
            parent_logger=agg,
            num_trials=args.trials,
            seed=args.seed,
            max_steps=args.max_steps if args.max_steps else 50 * n * n,
            max_consecutive_failures=5 * n * n,
        )
        results = search.run()
        if args.save and results:
            search.save([r for r in results if r.is_k4_free])

    if not results:
        print(f"[n={n}] no result"); return
    print(f"\n  add_remove_weighted  n={n}  weight={args.weight}  beta={args.beta}  "
          f"stop={args.stop}{'='+str(args.target) if args.stop!='none' else ''}  trials={args.trials}")
    print("  " + "-" * 70)
    for i, r in enumerate(results):
        added = r.metadata.get("added", 0)
        removed = r.metadata.get("removed", 0)
        print(f"  trial {i:>2}: c_log={_fmt(r.c_log)}  α={r.alpha:>3}  "
              f"d_max={r.d_max:>3}  |E|={r.metadata.get('edges', 0):>5}  "
              f"+{added}/-{removed}")
    best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
    print(f"  best c_log = {_fmt(best.c_log)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--weight", choices=list(SCORERS), required=True)
    ap.add_argument("--stop", choices=list(STOP_BUILDERS) + ["none"], default="none")
    ap.add_argument("--target", default=0)
    ap.add_argument("--beta", type=float, default=4.0)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
