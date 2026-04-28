#!/usr/bin/env python3
"""
experiments/random/compare_all.py
==================================
Run every random baseline under one harness and print a comparison
table of best c_log per N.

Methods covered:
  uniform_alpha       add_edges.py            uniform add-only,   stop=alpha
  uniform_ar_alpha    add_remove_edges.py     uniform add+remove, stop=alpha
  bohman_keevash      bohman_keevash.py       uniform add-only,   stop=saturation
  w_d_min_sat         add_edges_weighted          weight=d_min,   stop=none
  w_alpha_sat         add_edges_weighted          weight=alpha,   stop=none
  w_c_log_sat         add_edges_weighted          weight=c_log,   stop=none
  ar_target_reg       add_remove_edges_weighted   weight=target_regular, stop=edges
  ar_alpha            add_remove_edges_weighted   weight=alpha,   stop=edges
  ar_c_log            add_remove_edges_weighted   weight=c_log,   stop=edges

α scoring is the greedy lower bound (alpha_lb), not CP-SAT.
"""

from __future__ import annotations

import os
import sys
import time
from math import log

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk

import add_edges_weighted as W
import add_edges as A


def _edges_target(n: int) -> int:
    return max(1, round(n ** (5 / 3) / 2))


def _alpha_target(n: int) -> int:
    d = max(2.0, n ** (2 / 3))
    return max(2, round(n * log(d) / d))


def _run(name, n, trials, seed, build_walk):
    t0 = time.monotonic()
    with AggregateLogger(name=name) as agg:
        search = build_walk(n, trials, seed, agg)
        results = search.run()
    dt = time.monotonic() - t0
    if not results:
        return None, dt
    best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
    return best, dt


# ── walk factories ────────────────────────────────────────────────────────

def w_uniform_alpha(n, trials, seed, agg):
    return EdgeFlipWalk(
        n=n,
        stop_fn=A.stop_alpha(_alpha_target(n)),
        propose_from_valid_moves_fn=A.propose_adds_only,
        top_k=1, verbosity=0, parent_logger=agg,
        num_trials=trials, seed=seed,
        max_steps=50 * n * n, max_consecutive_failures=5 * n * n,
    )

def w_uniform_ar_alpha(n, trials, seed, agg):
    """Uniform add+remove with α-stop (no scoring; removes give the
    walk room to dodge a high-d_max plateau before the α target hits)."""
    from add_remove_edges import propose_adds_and_removes as ar_prop  # type: ignore
    return EdgeFlipWalk(
        n=n,
        stop_fn=A.stop_alpha(_alpha_target(n)),
        propose_from_valid_moves_fn=ar_prop,
        top_k=1, verbosity=0, parent_logger=agg,
        num_trials=trials, seed=seed,
        max_steps=50 * n * n, max_consecutive_failures=5 * n * n,
    )

def w_bk(n, trials, seed, agg):
    from bohman_keevash import propose_adds_only as bk_prop  # type: ignore
    return EdgeFlipWalk(
        n=n,
        stop_fn=None,
        propose_from_valid_moves_fn=bk_prop,
        n_candidates=1,
        top_k=1, verbosity=0, parent_logger=agg,
        num_trials=trials, seed=seed,
        max_steps=10 * n * n, max_consecutive_failures=1,
    )

def _w_weighted_sat(weight):
    def factory(n, trials, seed, agg):
        return EdgeFlipWalk(
            n=n,
            stop_fn=None,
            propose_from_valid_moves_fn=W.propose_adds_only,
            batch_score_fn=W.SCORERS[weight],
            beta=4.0,
            top_k=1, verbosity=0, parent_logger=agg,
            num_trials=trials, seed=seed,
            max_steps=10 * n * n, max_consecutive_failures=1,
        )
    return factory

def _w_addremove(weight):
    import add_remove_edges_weighted as AR  # type: ignore
    def factory(n, trials, seed, agg):
        return EdgeFlipWalk(
            n=n,
            stop_fn=W.STOP_BUILDERS["edges"](_edges_target(n)),
            propose_from_valid_moves_fn=AR.propose_adds_and_removes,
            batch_score_fn=AR.SCORERS[weight],
            beta=4.0,
            top_k=1, verbosity=0, parent_logger=agg,
            num_trials=trials, seed=seed,
            max_steps=20 * n * n, max_consecutive_failures=5 * n * n,
        )
    return factory


METHODS = [
    ("uniform_alpha",   w_uniform_alpha),
    ("uniform_ar_alpha",w_uniform_ar_alpha),
    ("bohman_keev",     w_bk),
    ("w_d_min_sat",     _w_weighted_sat("d_min")),
    ("w_alpha_sat",     _w_weighted_sat("alpha")),
    ("w_c_log_sat",     _w_weighted_sat("c_log")),
    ("ar_target_reg",   _w_addremove("target_regular")),
    ("ar_alpha",        _w_addremove("alpha")),
    ("ar_c_log",        _w_addremove("c_log")),
]


def main():
    Ns = [10, 20, 30, 40, 50]
    trials = 3
    seed = 0

    table: dict[int, dict[str, tuple]] = {n: {} for n in Ns}

    for n in Ns:
        print(f"\n=== N={n} ===")
        for name, factory in METHODS:
            best, dt = _run(name, n, trials, seed, factory)
            if best is None or best.c_log is None:
                print(f"  {name:<14}  no result  ({dt:.1f}s)"); continue
            c = best.c_log
            table[n][name] = (c, best.alpha, best.d_max, best.metadata.get("edges", 0), dt)
            print(f"  {name:<14}  c_log={c:.4f}  α={best.alpha:>3}  d={best.d_max:>3}  "
                  f"|E|={best.metadata.get('edges',0):>5}  ({dt:.1f}s)")

    # ── summary ──
    print("\n" + "=" * 90)
    print(" Best c_log per N, method × N")
    print("=" * 90)
    hdr = f"  {'method':<14}" + "".join(f"{n:>9}" for n in Ns)
    print(hdr)
    print("  " + "-" * (14 + 9 * len(Ns)))
    for name, _ in METHODS:
        row = f"  {name:<14}"
        for n in Ns:
            v = table[n].get(name)
            row += f"{v[0]:>9.4f}" if v else f"{'—':>9}"
        print(row)

    # winner per N
    print("  " + "-" * (14 + 9 * len(Ns)))
    win_row = f"  {'WINNER':<14}"
    for n in Ns:
        best = min(table[n].items(), key=lambda kv: kv[1][0]) if table[n] else None
        win_row += f"{best[0][:8]:>9}" if best else f"{'—':>9}"
    print(win_row)


if __name__ == "__main__":
    main()
