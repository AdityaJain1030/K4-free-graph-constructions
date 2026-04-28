#!/usr/bin/env python3
"""
experiments/random/bohman_keevash.py
=====================================
Bohman–Keevash random K4-free process, built on EdgeFlipWalk.

Algorithm:
  start empty → repeatedly add a uniformly random K4-safe non-edge →
  stop at saturation (no safe edge remains).

Theory a.a.s. as N → ∞ (Wolfovitz 2010, arXiv:1008.4044):
  |E| = Θ(N^{8/5} (ln N)^{1/5}),
  α   = O(N^{3/5} (ln N)^{1/5}),
  Δ   ≈ Θ(N^{3/5} (ln N)^{1/5}).

Usage
-----
    # single run
    python experiments/random/bohman_keevash.py --n 50 --trials 5

    # scaling sweep + log-log fit vs theory
    python experiments/random/bohman_keevash.py --sweep \
        --n-min 10 --n-max 80 --trials 10
"""

from __future__ import annotations

import argparse
import os
import sys
from math import log

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk


# ── proposer: uniform over valid ADD moves only ────────────────────────────
# At saturation the valid-add set is empty → walk fails this step → with
# max_consecutive_failures=1 the trial halts cleanly.

def propose_adds_only(adj, valid_moves, info, rng, k):
    adds = [m for m in valid_moves if m[2]]
    if not adds:
        return []
    if k is None or k >= len(adds):
        return adds
    idx = rng.choice(len(adds), size=k, replace=False)
    return [adds[i] for i in idx]


def run_one(n: int, num_trials: int, seed: int, agg) -> list:
    search = EdgeFlipWalk(
        n=n,
        stop_fn=None,                                  # run to saturation
        propose_from_valid_moves_fn=propose_adds_only,
        n_candidates=1,                                # uniform 1-sample per step
        top_k=1,
        verbosity=0,
        parent_logger=agg,
        num_trials=num_trials,
        seed=seed,
        max_steps=10 * n * n,
        max_consecutive_failures=1,                    # saturation = halt
    )
    return search.run()


# ── single-N driver ────────────────────────────────────────────────────────

def cmd_single(args) -> None:
    with AggregateLogger(name="bohman_keevash") as agg:
        results = run_one(args.n, args.trials, args.seed, agg)
    if not results:
        print(f"[n={args.n}] no result")
        return
    print(f"\n  bohman_keevash  n={args.n}  trials={args.trials}")
    print("  " + "-" * 60)
    for i, r in enumerate(results):
        print(f"  trial {i:>2}: c_log={r.c_log:.4f}  α={r.alpha:>3}  "
              f"d_max={r.d_max:>3}  |E|={r.metadata.get('edges', 0):>5}")
    best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
    print(f"  best c_log = {best.c_log:.4f}")


# ── sweep + theory check ───────────────────────────────────────────────────

def _fit_loglog(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Return (slope, intercept) of log y = slope * log x + intercept."""
    lx = np.log(np.asarray(xs, dtype=float))
    ly = np.log(np.asarray(ys, dtype=float))
    slope, intercept = np.polyfit(lx, ly, 1)
    return float(slope), float(intercept)


def cmd_sweep(args) -> None:
    rows: list[dict] = []
    print(f"\n  bohman_keevash sweep  N={args.n_min}..{args.n_max}  "
          f"trials={args.trials}  seed={args.seed}")
    print("  " + "-" * 72)
    print(f"  {'N':>4}  {'best c_log':>10}  {'med α':>6}  {'med d':>6}  {'med |E|':>8}")

    with AggregateLogger(name="bohman_keevash_sweep") as agg:
        for n in range(args.n_min, args.n_max + 1, args.step):
            results = run_one(n, args.trials, args.seed, agg)
            if not results:
                continue
            alphas = [r.alpha for r in results]
            dmax = [r.d_max for r in results]
            edges = [r.metadata.get("edges", 0) for r in results]
            clogs = [r.c_log for r in results if r.c_log is not None]
            best_c = min(clogs) if clogs else float("nan")
            row = {
                "n": n,
                "best_c_log": best_c,
                "med_alpha": float(np.median(alphas)),
                "med_d_max": float(np.median(dmax)),
                "med_edges": float(np.median(edges)),
            }
            rows.append(row)
            print(f"  {n:>4}  {best_c:>10.4f}  {row['med_alpha']:>6.1f}  "
                  f"{row['med_d_max']:>6.1f}  {row['med_edges']:>8.1f}")

    if len(rows) < 4:
        print("\nNot enough points for a fit.")
        return

    ns = [r["n"] for r in rows]
    s_e, _ = _fit_loglog(ns, [r["med_edges"] for r in rows])
    s_a, _ = _fit_loglog(ns, [r["med_alpha"] for r in rows])
    s_d, _ = _fit_loglog(ns, [r["med_d_max"] for r in rows])
    s_c, _ = _fit_loglog(ns, [r["best_c_log"] for r in rows])

    print("\n  log-log fit  (median per N, except c_log = best per N)")
    print("  " + "-" * 72)
    print(f"    |E|   ~ N^{s_e:.3f}    theory: N^{8/5:.3f} (ln N)^{1/5:.2f}  (Wolfovitz 2010)")
    print(f"    α     ~ N^{s_a:.3f}    theory: N^{3/5:.3f} (ln N)^{1/5:.2f}  (Wolfovitz 2010)")
    print(f"    d_max ~ N^{s_d:.3f}    theory: N^{3/5:.3f} (ln N)^{1/5:.2f}  (parallels α)")
    print(f"    c_log ~ N^{s_c:.3f}    theory: N^{1/5:.2f} / (ln N)^{3/5:.2f}")

    de = s_e - 8 / 5
    da = s_a - 3 / 5
    print("\n  Theory match:")
    print(f"    |E|  exponent gap: {de:+.3f}   "
          f"({'OK' if abs(de) < 0.15 else 'large — finite-N polylog'})")
    print(f"    α    exponent gap: {da:+.3f}   "
          f"({'OK' if abs(da) < 0.15 else 'large — finite-N polylog'})")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")

    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--trials", type=int, default=5)
    ap.add_argument("--seed", type=int, default=20260427)
    ap.add_argument("--sweep", action="store_true")
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=60)
    ap.add_argument("--step", type=int, default=5)

    args = ap.parse_args()
    if args.sweep:
        cmd_sweep(args)
    else:
        if args.n is None:
            ap.error("--n required (or use --sweep)")
        cmd_single(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
