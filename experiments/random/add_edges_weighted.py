#!/usr/bin/env python3
"""
experiments/random/add_edges_weighted.py
=========================================
Random K4-free edge-addition with a softmax-weighted choice over candidate
adds, built on EdgeFlipWalk.

Weighting modes (`--weight`):
  d_min   prefer adding edges between low-degree endpoints (regularity bias)
  alpha   prefer adds that minimise the surrogate α after the move
  c_log   prefer adds that minimise surrogate c_log after the move

Stop modes (same as add_edges.py):
  edges --target T   halt when |E| >= T
  d_max --target T   halt when Δ >= T
  alpha --target T   halt when α(G) <= T  (CP-SAT every 5 steps)
  none               run until saturation (Bohman–Keevash-style halt)

Usage
-----
    python experiments/random/add_edges_weighted.py \
        --n 25 --weight d_min --stop edges --target 100 --beta 4
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Callable

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk
from utils.alpha_surrogate import alpha_lb, c_log_surrogate
from utils.graph_props import alpha_cpsat


# ── stop-fns ───────────────────────────────────────────────────────────────

def stop_edges(target):  return lambda adj, info: int(adj.sum()) // 2 >= target
def stop_d_max(target):
    def f(adj, info):
        return adj.size > 0 and int(adj.sum(axis=1).max()) >= target
    return f
def stop_alpha(target, every=5):
    def f(adj, info):
        s = info.get("steps", 0)
        if s == 0 or s % every: return False
        a, _ = alpha_cpsat(adj, time_limit=10.0)
        return a > 0 and a <= target
    return f

STOP_BUILDERS = {"edges": stop_edges, "d_max": stop_d_max, "alpha": stop_alpha}


# ── add-only proposer ──────────────────────────────────────────────────────

def propose_adds_only(adj, valid_moves, info, rng, k):
    adds = [m for m in valid_moves if m[2]]
    if not adds:
        return []
    return adds  # let scorer + softmax pick


# ── batch scorers — higher score = preferred (softmax over `score`) ─────────
# All return a vector of scores aligned with `moves`. Walk handles softmax.

def score_d_min(adj: np.ndarray, moves: list, info: dict) -> np.ndarray:
    deg = adj.sum(axis=1).astype(np.float64)
    out = np.empty(len(moves), dtype=np.float64)
    for i, (u, v, _) in enumerate(moves):
        out[i] = -(deg[u] + deg[v])
    return out


# Tiebreaker scale: alpha_lb / c_log_surrogate return integers / coarse floats,
# so many candidates collide. Add a small d_min component so degree breaks ties
# without overpowering the primary signal.
_TIEBREAK = 0.05  # secondary signal; α-LB integer step (1.0) still dominates


def score_alpha(adj: np.ndarray, moves: list, info: dict) -> np.ndarray:
    """Primary: -alpha_lb post-add. Tiebreaker: -d_min on endpoints."""
    rng = np.random.default_rng(int(info.get("steps", 0)))
    deg = adj.sum(axis=1).astype(np.float64)
    out = np.empty(len(moves), dtype=np.float64)
    work = adj.copy()
    for i, (u, v, _) in enumerate(moves):
        work[u, v] = work[v, u] = 1
        a = float(alpha_lb(work, restarts=4, rng=rng))
        out[i] = -a - _TIEBREAK * (deg[u] + deg[v])
        work[u, v] = work[v, u] = 0
    return out


def score_c_log(adj: np.ndarray, moves: list, info: dict) -> np.ndarray:
    """Primary: -c_log_surrogate post-add. Tiebreaker: -d_min on endpoints."""
    rng = np.random.default_rng(int(info.get("steps", 0)))
    deg = adj.sum(axis=1).astype(np.float64)
    out = np.empty(len(moves), dtype=np.float64)
    work = adj.copy()
    for i, (u, v, _) in enumerate(moves):
        work[u, v] = work[v, u] = 1
        c = c_log_surrogate(work, lb_restarts=4, rng=rng)
        primary = -c if np.isfinite(c) else -1e6
        out[i] = primary - _TIEBREAK * (deg[u] + deg[v])
        work[u, v] = work[v, u] = 0
    return out


SCORERS = {"d_min": score_d_min, "alpha": score_alpha, "c_log": score_c_log}


# ── driver ────────────────────────────────────────────────────────────────

def _fmt(x): return "—" if x is None else f"{x:.4f}"


def run(args) -> None:
    n = args.n
    stop_fn = None if args.stop == "none" else STOP_BUILDERS[args.stop](int(args.target))
    scorer = SCORERS[args.weight]

    with AggregateLogger(name=f"add_edges_weighted_{args.weight}") as agg:
        search = EdgeFlipWalk(
            n=n,
            stop_fn=stop_fn,
            propose_from_valid_moves_fn=propose_adds_only,
            batch_score_fn=scorer,
            beta=args.beta,
            top_k=1,
            verbosity=0,
            parent_logger=agg,
            num_trials=args.trials,
            seed=args.seed,
            max_steps=50 * n * n,
            max_consecutive_failures=1 if stop_fn is None else 5 * n * n,
        )
        results = search.run()
        if args.save and results:
            search.save([r for r in results if r.is_k4_free])

    if not results:
        print(f"[n={n}] no result"); return
    print(f"\n  add_edges_weighted  n={n}  weight={args.weight}  beta={args.beta}  "
          f"stop={args.stop}{'='+str(args.target) if args.stop!='none' else ''}  trials={args.trials}")
    print("  " + "-" * 70)
    for i, r in enumerate(results):
        print(f"  trial {i:>2}: c_log={_fmt(r.c_log)}  α={r.alpha:>3}  "
              f"d_max={r.d_max:>3}  |E|={r.metadata.get('edges', 0):>5}")
    best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
    print(f"  best c_log = {_fmt(best.c_log)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--weight", choices=list(SCORERS), required=True)
    ap.add_argument("--stop", choices=list(STOP_BUILDERS) + ["none"], default="none")
    ap.add_argument("--target", default=0)
    ap.add_argument("--beta", type=float, default=4.0,
                    help="softmax temperature; higher = greedier")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
