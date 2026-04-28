"""
scripts/run_n23_ablation.py
============================
N=23 surrogate-vs-exact ablation plus warm-mixed diagnostic.

Runs (all at N=23, multiset-relevant budget):
  (1)  k-fixed cold, pure 2-switch, surrogate ranking (baseline).
  (1a) k-fixed cold, pure 2-switch, EXACT α ranking (ablation).
  (1b) k-fixed cold, pure 2-switch, surrogate but top_k_verify widened
       to 20. Cheap follow-up if (1a) beats (1).
  (5)  warm-mixed: start from SAT frontier, mixed 2-switch+flip,
       spread_cap=2. Closes the warm/cold × pure/mixed 2×2.

Logs feasible-swap-count distribution per run so move-graph sparsity
can be distinguished from plateau-diameter in the diagnosis.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db.db import DB
from search.stochastic_walk.switch_tabu import (
    switch_tabu_chain,
    switch_tabu_chain_mixed,
    _build_multiset_init,
    SwitchTabuResult,
)

FRONTIER_C = 0.75271
FRONTIER_ALPHA = 6


def _fetch_sat_frontier_adj() -> np.ndarray | None:
    with DB() as db:
        rows = db.query(n=23, source=["sat_near_regular_nonreg", "server_sat_exact"])
        rows = [r for r in rows if r.get("c_log") is not None]
        rows.sort(key=lambda r: r["c_log"])
        if not rows:
            return None
        G = db.nx(rows[0]["graph_id"])
        return np.array(nx.to_numpy_array(G, dtype=np.uint8)) if G is not None else None


def _pool_stats(ps: list[int]) -> str:
    if not ps:
        return "no samples"
    return (f"n={len(ps)} min={min(ps)} median={statistics.median(ps):.0f} "
            f"mean={statistics.mean(ps):.1f} max={max(ps)}")


def _report(label: str, res: SwitchTabuResult, elapsed: float):
    hit = "✓" if res.best_alpha <= FRONTIER_ALPHA else "·"
    gap = res.best_c_log - FRONTIER_C
    degs = res.best_adj.sum(axis=1)
    ms = (f"{{{int(degs.min())}:{int((degs == degs.min()).sum())}, "
          f"{int(degs.max())}:{int((degs == degs.max()).sum())}}}")
    print(f"  {hit} {label:<38} α={res.best_alpha}  c_log={res.best_c_log:.4f}  "
          f"gap={gap:+.4f}  final_m={int(degs.sum()//2)} final_multiset={ms}")
    print(f"    iters={res.n_iters} accepted={res.n_accepted} aspiration={res.n_aspiration} "
          f"ils_restarts={res.n_restarts}  elapsed={elapsed:.1f}s")
    print(f"    pool_sizes (feasible swaps/iter): {_pool_stats(res.pool_sizes)}")
    distinct_mk = len(set(zip(res.m_trajectory, res.k_trajectory)))
    print(f"    (m,k) distinct states visited: {distinct_mk}  "
          f"move_kinds={dict(res.move_kind_counts)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n_iters", type=int, default=800)
    p.add_argument("--n_restarts_chain", type=int, default=3)
    p.add_argument("--swap_sample", type=int, default=60)
    p.add_argument("--flip_sample", type=int, default=30)
    p.add_argument("--lb_restarts", type=int, default=12)
    p.add_argument("--tabu_len", type=int, default=14)
    p.add_argument("--patience", type=int, default=60)
    p.add_argument("--perturb_swaps", type=int, default=5)
    p.add_argument("--time_limit_s", type=float, default=90.0)
    p.add_argument("--seed", type=int, default=0)
    args = p.parse_args()

    N = 23
    target_deg = [3, 3] + [4] * 21  # (m=45, k=2)
    print(f"=== N={N} ablation  frontier=0.7527 (α=6)  budget n_iters={args.n_iters} x "
          f"{args.n_restarts_chain} restarts ===\n")

    def _best_over_restarts(make_init, run_chain):
        best = None
        for r in range(args.n_restarts_chain):
            rng_chain = np.random.default_rng(args.seed * 1000 + r)
            init = make_init(rng_chain)
            if init is None:
                continue
            t0 = time.monotonic()
            res = run_chain(init, rng_chain)
            el = time.monotonic() - t0
            if best is None or res.best_c_log < best[0].best_c_log:
                best = (res, el)
        return best

    # (1) baseline: k-fixed, surrogate top-K=6
    print("--- (1) k-fixed cold, surrogate α_lb ranking, top_k=6 ---")
    res1 = _best_over_restarts(
        lambda rng: _build_multiset_init(N, target_deg, rng),
        lambda init, rng: switch_tabu_chain(
            init, n_iters=args.n_iters, sample_size=args.swap_sample, top_k=6,
            lb_restarts=args.lb_restarts, tabu_len=args.tabu_len,
            patience=args.patience, perturb_swaps=args.perturb_swaps,
            rng=rng, time_limit_s=args.time_limit_s, use_exact_score=False,
        ),
    )
    if res1: _report("(1) k-fixed, surrogate top-6", res1[0], res1[1])
    print()

    # (1a) ablation: exact α ranking on every candidate
    print("--- (1a) k-fixed cold, EXACT α ranking on every candidate ---")
    res1a = _best_over_restarts(
        lambda rng: _build_multiset_init(N, target_deg, rng),
        lambda init, rng: switch_tabu_chain(
            init, n_iters=args.n_iters, sample_size=args.swap_sample, top_k=6,
            lb_restarts=args.lb_restarts, tabu_len=args.tabu_len,
            patience=args.patience, perturb_swaps=args.perturb_swaps,
            rng=rng, time_limit_s=args.time_limit_s, use_exact_score=True,
        ),
    )
    if res1a: _report("(1a) k-fixed, exact every candidate", res1a[0], res1a[1])
    print()

    # (1b) wider-K surrogate (conditional follow-up if 1a beats 1)
    print("--- (1b) k-fixed cold, surrogate α_lb ranking, top_k=20 ---")
    res1b = _best_over_restarts(
        lambda rng: _build_multiset_init(N, target_deg, rng),
        lambda init, rng: switch_tabu_chain(
            init, n_iters=args.n_iters, sample_size=args.swap_sample, top_k=20,
            lb_restarts=args.lb_restarts, tabu_len=args.tabu_len,
            patience=args.patience, perturb_swaps=args.perturb_swaps,
            rng=rng, time_limit_s=args.time_limit_s, use_exact_score=False,
        ),
    )
    if res1b: _report("(1b) k-fixed, surrogate top-20", res1b[0], res1b[1])
    print()

    # (5) warm-mixed cap=2 from SAT frontier
    print("--- (5) warm-mixed: start from SAT frontier, mixed 2-switch+flip, cap=2 ---")
    warm_adj = _fetch_sat_frontier_adj()
    if warm_adj is None:
        print("  SKIP — no SAT frontier row at N=23.")
        res5 = None
    else:
        res5 = _best_over_restarts(
            lambda rng: warm_adj.copy(),
            lambda init, rng: switch_tabu_chain_mixed(
                init, n_iters=args.n_iters,
                sample_size_swap=args.swap_sample,
                sample_size_flip=args.flip_sample,
                top_k=6, lb_restarts=args.lb_restarts, tabu_len=args.tabu_len,
                patience=args.patience, perturb_swaps=args.perturb_swaps,
                spread_cap=2, rng=rng, time_limit_s=args.time_limit_s,
            ),
        )
        if res5: _report("(5) warm-mixed cap=2", res5[0], res5[1])
    print()

    # quick decision help
    def _a(r): return r[0].best_alpha if r else None
    def _c(r): return r[0].best_c_log if r else None
    print("=== decision table ===")
    print(f"  (1)  surrogate top-6 : α={_a(res1)} c={_c(res1):.4f}" if res1 else "  (1)  none")
    print(f"  (1a) exact           : α={_a(res1a)} c={_c(res1a):.4f}" if res1a else "  (1a) none")
    print(f"  (1b) surrogate top-20: α={_a(res1b)} c={_c(res1b):.4f}" if res1b else "  (1b) none")
    print(f"  (5)  warm-mixed cap=2: α={_a(res5)} c={_c(res5):.4f}" if res5 else "  (5)  none")


if __name__ == "__main__":
    main()
