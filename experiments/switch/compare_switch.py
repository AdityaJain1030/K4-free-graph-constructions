#!/usr/bin/env python3
"""
experiments/switch/compare_switch.py
=====================================
Compare two 2-stage K4-free search pipelines:

  Pipeline A — RandomRegularSwitchSearch:
    Stage 1: random K4-free graph with hard degree cap d ≈ n^{2/3},
             sweeping d in {target-2 .. target+2}
    Stage 2: rebalancing switch hill-climb (greedy α + spread gate)

  Pipeline B — EdgeFlipWalk + EdgeSwitchWalk:
    Stage 1: EdgeFlipWalk with degree-cap score (add-only, return -inf if
             either endpoint ≥ d_cap), same d_cap sweep as Pipeline A
    Stage 2: EdgeSwitchWalk, scored by −alpha_approx

Both pipelines sweep the same d_cap values × num_trials and pick the best
result by c_log. Same seed across both.

Usage
-----
    micromamba run -n k4free python experiments/switch/compare_switch.py
    micromamba run -n k4free python experiments/switch/compare_switch.py \
        --n-max 40 --trials 5 --alpha-restarts 32 --save
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from math import log

import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk
from search.stochastic_walk.edge_switch_walk import EdgeSwitchWalk
from search.stochastic_walk.random_regular_switch import RandomRegularSwitchSearch
from utils.graph_props import alpha_approx, alpha_cpsat


# ── d_cap sweep (mirrors RandomRegularSwitchSearch._default_degrees) ──────

def _d_caps(n: int) -> list[int]:
    target = max(3, round(n ** (2 / 3)))
    candidates = sorted({
        max(3, target - 2), max(3, target - 1),
        target, target + 1, target + 2,
    })
    return [d for d in candidates if d <= n - 1]


def _alpha_target(n: int) -> int:
    d = max(2.0, n ** (2 / 3))
    return max(2, round(n * log(d) / d))


def _fmt(x) -> str:
    return "—" if x is None else f"{x:.4f}"


# ── stage-1 score: add-only with hard degree cap ───────────────────────────

def score_degree_cap(d_cap: int):
    def _s(adj, u, v, is_add, info, context) -> float:
        if not is_add:
            return float("-inf")
        if "deg" not in context:
            context["deg"] = adj.sum(axis=1)
        deg = context["deg"]
        if deg[u] >= d_cap or deg[v] >= d_cap:
            return float("-inf")
        return 0.0
    return _s


# ── stage-2 score: −alpha_approx per switch ────────────────────────────────

def score_neg_alpha_factory(restarts: int = 32):
    def _s(adj, move, info, context) -> float:
        a, b, c, d, rewiring = move
        if rewiring == "ad_bc":
            c, d = d, c
        if "alpha_now" not in context:
            context["alpha_now"] = alpha_approx(adj, restarts=restarts)
        alpha_now = context["alpha_now"]
        adj[a, b] = adj[b, a] = 0
        adj[c, d] = adj[d, c] = 0
        adj[a, c] = adj[c, a] = 1
        adj[b, d] = adj[d, b] = 1
        alpha_new = alpha_approx(adj, restarts=restarts)
        adj[a, c] = adj[c, a] = 0
        adj[b, d] = adj[d, b] = 0
        adj[a, b] = adj[b, a] = 1
        adj[c, d] = adj[d, c] = 1
        return float(alpha_now - alpha_new)
    return _s


def stop_alpha(target: int, every: int = 5):
    def f(adj, info) -> bool:
        s = info.get("steps", 0)
        if s == 0 or s % every != 0:
            return False
        a, _ = alpha_cpsat(adj, time_limit=10.0)
        return a > 0 and a <= target
    return f


# ── pipeline B: one (d_cap, seed) run ──────────────────────────────────────

def _run_b_one(n, d_cap, num_trials, seed, alpha_restarts, n_cands, agg):
    alpha_target = _alpha_target(n)

    stage1 = EdgeFlipWalk(
        n=n,
        stop_fn=None,  # run until saturation — degree cap in score enforces the limit
        score_fn=score_degree_cap(d_cap),
        num_trials=num_trials,
        seed=seed,
        max_steps=50 * n * n,
        max_consecutive_failures=5 * n * n,
        top_k=1,
        verbosity=0,
        parent_logger=agg,
    )
    s1 = stage1.run()
    if not s1:
        return None
    seed_result = max(s1, key=lambda r: r.metadata.get("edges", 0))

    stage2 = EdgeSwitchWalk(
        n=n,
        seed_graph=seed_result.G,
        stop_fn=stop_alpha(alpha_target),
        score_fn=score_neg_alpha_factory(restarts=alpha_restarts),
        n_candidates=n_cands,  # cap per-step scoring cost
        num_trials=num_trials,
        seed=seed,
        max_steps=50 * n * n,
        max_consecutive_failures=5 * n * n,
        top_k=1,
        verbosity=0,
        parent_logger=agg,
    )
    s2 = stage2.run()
    return s2 or None


# ── pipeline runners ────────────────────────────────────────────────────────

def run_pipeline_a(n, num_trials, seed, agg, do_save):
    search = RandomRegularSwitchSearch(
        n=n, num_trials=num_trials, seed=seed,
        top_k=1, verbosity=0, parent_logger=agg,
    )
    results = search.run()
    if do_save and results:
        search.save([r for r in results if r.is_k4_free])
    return results or None


def run_pipeline_b(n, num_trials, seed, alpha_restarts, n_cands, agg, do_save):
    all_results = []
    for d_cap in _d_caps(n):
        rs = _run_b_one(n, d_cap, num_trials, seed, alpha_restarts, n_cands, agg)
        if rs:
            all_results.extend(rs)
    return all_results or None


def _best(results) -> object | None:
    if not results:
        return None
    valid = [r for r in results if r.c_log is not None]
    return min(valid, key=lambda r: r.c_log) if valid else None


# ── main sweep ─────────────────────────────────────────────────────────────

def run(n_min, n_max, num_trials, seed, alpha_restarts, n_cands, do_save):
    rows = []

    with AggregateLogger(name="compare_switch") as agg:
        for n in range(n_min, n_max + 1):
            if n < 4:
                continue

            t0 = time.monotonic()
            ra = run_pipeline_a(n, num_trials, seed, agg, do_save)
            dt_a = time.monotonic() - t0

            t0 = time.monotonic()
            rb = run_pipeline_b(n, num_trials, seed, alpha_restarts, n_cands, agg, do_save)
            dt_b = time.monotonic() - t0

            best_a = _best(ra)
            best_b = _best(rb)
            ca = best_a.c_log if best_a else None
            cb = best_b.c_log if best_b else None
            aa = best_a.alpha if best_a else None
            ab = best_b.alpha if best_b else None

            rows.append(dict(n=n, c_a=ca, c_b=cb, alpha_a=aa, alpha_b=ab,
                             dt_a=dt_a, dt_b=dt_b))

            winner = ""
            if ca is not None and cb is not None:
                if cb < ca - 1e-6:   winner = " ← B wins"
                elif ca < cb - 1e-6: winner = " ← A wins"
                else:                winner = " (tie)"

            print(
                f"  n={n:>3}  "
                f"A: c={_fmt(ca)} α={aa!s:>3} ({dt_a:.1f}s)  "
                f"B: c={_fmt(cb)} α={ab!s:>3} ({dt_b:.1f}s)"
                f"{winner}"
            )

    print()
    print("=" * 78)
    print("  compare_switch summary")
    print("  A = RandomRegularSwitchSearch")
    print("  B = EdgeFlipWalk (d-cap) → EdgeSwitchWalk (−α)")
    print("=" * 78)
    print(f"{'n':>4}  {'c_log A':>10}  {'c_log B':>10}  {'α A':>4}  {'α B':>4}  {'winner':>8}")
    print("-" * 78)
    for r in rows:
        ca, cb = r["c_a"], r["c_b"]
        if ca is not None and cb is not None:
            winner = "B" if cb < ca - 1e-6 else ("A" if ca < cb - 1e-6 else "tie")
        else:
            winner = "—"
        print(f"{r['n']:>4}  {_fmt(ca):>10}  {_fmt(cb):>10}  "
              f"{r['alpha_a']!s:>4}  {r['alpha_b']!s:>4}  {winner:>8}")

    a_wins = sum(1 for r in rows if r["c_a"] and r["c_b"] and r["c_a"] < r["c_b"] - 1e-6)
    b_wins = sum(1 for r in rows if r["c_a"] and r["c_b"] and r["c_b"] < r["c_a"] - 1e-6)
    ties   = sum(1 for r in rows if r["c_a"] and r["c_b"] and abs(r["c_a"] - r["c_b"]) <= 1e-6)
    print(f"\n  A wins: {a_wins}  B wins: {b_wins}  ties: {ties}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-min", type=int, default=4)
    ap.add_argument("--n-max", type=int, default=30)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--alpha-restarts", type=int, default=16)
    ap.add_argument("--n-cands", type=int, default=50,
                    help="Candidates per step in stage-2 EdgeSwitchWalk. "
                         "Each is K4-checked + alpha_approx-scored, so keep small.")
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()
    run(args.n_min, args.n_max, args.trials, args.seed,
        args.alpha_restarts, args.n_cands, args.save)

    return 0


if __name__ == "__main__":
    sys.exit(main())
