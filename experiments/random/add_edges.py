#!/usr/bin/env python3
"""
experiments/random/add_edges.py
================================
Simple random edge-addition experiment built on EdgeFlipWalk.

Only proposes ADD moves (never removes). Walk halts when one of:
  --stop edges  --target T   stop when |E| >= T
  --stop d_max  --target T   stop when max degree >= T
  --stop alpha  --target T   stop when α(G) <= T

Usage
-----
    python experiments/random/add_edges.py --n 20 --stop edges --target 40
    python experiments/random/add_edges.py --n 20 --stop d_max --target 6
    python experiments/random/add_edges.py --n 20 --stop alpha --target 5
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
from utils.graph_props import alpha_cpsat


# ── stop-fns: (adj, info) -> bool ──────────────────────────────────────────

def stop_edges(target: int) -> Callable[[np.ndarray, dict], bool]:
    return lambda adj, info: int(adj.sum()) // 2 >= target


def stop_d_max(target: int) -> Callable[[np.ndarray, dict], bool]:
    def f(adj, info):
        if adj.size == 0:
            return target <= 0
        return int(adj.sum(axis=1).max()) >= target
    return f


def stop_alpha(target: int, every: int = 5) -> Callable[[np.ndarray, dict], bool]:
    def f(adj, info):
        s = info.get("steps", 0)
        if s == 0 or s % every != 0:
            return False
        a, _ = alpha_cpsat(adj, time_limit=10.0)
        return a > 0 and a <= target
    return f


STOP_BUILDERS = {"edges": stop_edges, "d_max": stop_d_max, "alpha": stop_alpha}


# ── proposer: uniform over valid ADD moves only ────────────────────────────

def propose_adds_only(adj, valid_moves, info, rng, k):
    adds = [m for m in valid_moves if m[2]]
    if not adds:
        return []
    if k is None or k >= len(adds):
        return adds
    idx = rng.choice(len(adds), size=k, replace=False)
    return [adds[i] for i in idx]


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def run(n: int, stop: str, target, num_trials: int, seed: int,
        n_candidates: int | None, do_save: bool) -> None:
    stop_fn = STOP_BUILDERS[stop](target)

    with AggregateLogger(name="add_edges") as agg:
        search = EdgeFlipWalk(
            n=n,
            stop_fn=stop_fn,
            propose_from_valid_moves_fn=propose_adds_only,
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

    print(f"\n  add_edges  n={n}  stop={stop}  target={target}  trials={num_trials}")
    print("  " + "-" * 60)
    for i, r in enumerate(results):
        print(f"  trial {i:>2}: c_log={_fmt(r.c_log)}  α={r.alpha:>3}  "
              f"d_max={r.d_max:>3}  |E|={r.metadata.get('edges', 0):>4}  "
              f"added={r.metadata.get('added', 0):>4}")
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
    target = int(args.target)
    run(args.n, args.stop, target, args.trials, args.seed, args.n_cands, args.save)
    return 0


if __name__ == "__main__":
    sys.exit(main())
