"""
scripts/run_n23_composite.py
=============================
N=23 composite-score ablation. Factorial on (score type) × (top-K).

Score types:
  surrogate : sort candidates by α_lb, exact-verify top-K, pick min c_log.
  exact     : sort candidates by exact α, pick min c_log.
  composite : sort candidates by (exact α, α_lb) lex, pick min c_log.

top-K:
   6 : original tabu K — underpowered at 14% surrogate precision.
  60 : full pool — "K=pool size" regime. Tie-break does all the work.

Reports per-seed and aggregate find-rates for α≤8 and α≤7, plus
iter-at-first-reached for each α level and mean wall-clock per chain.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.stochastic_walk.switch_tabu import (
    switch_tabu_chain, _build_multiset_init, SwitchTabuResult,
)


def _run_one(init, rng, args, mode, K):
    """mode ∈ {surrogate, exact, composite}; K ∈ any positive int."""
    common = dict(
        n_iters=args.n_iters, sample_size=args.swap_sample, top_k=K,
        lb_restarts=args.lb_restarts, tabu_len=args.tabu_len,
        patience=args.patience, perturb_swaps=args.perturb_swaps,
        rng=rng, time_limit_s=args.time_limit_s,
    )
    if mode == "surrogate":
        return switch_tabu_chain(init, use_exact_score=False, composite_score=False, **common)
    if mode == "exact":
        return switch_tabu_chain(init, use_exact_score=True, composite_score=False, **common)
    if mode == "composite":
        return switch_tabu_chain(init, use_exact_score=False, composite_score=True, **common)
    raise ValueError(mode)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n_iters", type=int, default=800)
    p.add_argument("--n_seeds", type=int, default=8)
    p.add_argument("--swap_sample", type=int, default=60)
    p.add_argument("--lb_restarts", type=int, default=12)
    p.add_argument("--tabu_len", type=int, default=14)
    p.add_argument("--patience", type=int, default=60)
    p.add_argument("--perturb_swaps", type=int, default=5)
    p.add_argument("--time_limit_s", type=float, default=120.0)
    args = p.parse_args()

    N = 23
    target = [3, 3] + [4] * 21
    # (mode, K) conditions
    conditions = [
        ("surrogate", 6),
        ("surrogate", 60),
        ("composite", 6),
        ("composite", 60),
    ]
    results: dict[tuple[str, int], list[SwitchTabuResult]] = {c: [] for c in conditions}
    elapsed_map: dict[tuple[str, int], list[float]] = {c: [] for c in conditions}

    print(f"=== N=23 (score × K) factorial, {args.n_seeds} seeds, "
          f"n_iters={args.n_iters}, pool={args.swap_sample} ===\n")
    print(f"{'seed':>4}  {'mode':>10}  {'K':>3}  {'α':>2}  {'c_log':>7}  "
          f"{'iter@α=8':>8}  {'iter@α=7':>8}  {'elapsed_s':>9}")
    print("-" * 80)
    for seed in range(args.n_seeds):
        rng_init = np.random.default_rng(seed * 101 + 13)
        init = _build_multiset_init(N, target, rng_init)
        if init is None:
            continue
        for (mode, K) in conditions:
            rng_chain = np.random.default_rng(
                seed * 101 + 200 + (hash(mode) % 97) + K
            )
            t0 = time.monotonic()
            res = _run_one(init, rng_chain, args, mode, K)
            el = time.monotonic() - t0
            results[(mode, K)].append(res)
            elapsed_map[(mode, K)].append(el)
            it8 = res.alpha_first_reached.get(8, None)
            it7 = res.alpha_first_reached.get(7, None)
            it8s = "-" if it8 is None else str(it8)
            it7s = "-" if it7 is None else str(it7)
            print(f"{seed:>4}  {mode:>10}  {K:>3}  {res.best_alpha:>2}  "
                  f"{res.best_c_log:>7.4f}  {it8s:>8}  {it7s:>8}  {el:>9.1f}")
        print()

    print("=== find-rate summary ===")
    print(f"{'mode':>10}  {'K':>3}  {'α≤8':>5}  {'α≤7':>5}  "
          f"{'best α':>6}  {'best c':>7}  {'mean c':>7}  "
          f"{'med iter@8':>10}  {'med iter@7':>10}  {'mean s':>7}")
    for c in conditions:
        rs = results[c]
        ns = len(rs)
        hit8 = sum(1 for r in rs if r.best_alpha <= 8)
        hit7 = sum(1 for r in rs if r.best_alpha <= 7)
        best_a = min(r.best_alpha for r in rs)
        best_c = min(r.best_c_log for r in rs)
        mean_c = float(np.mean([r.best_c_log for r in rs]))
        it8s = [r.alpha_first_reached[8] for r in rs if 8 in r.alpha_first_reached]
        it7s = [r.alpha_first_reached[7] for r in rs if 7 in r.alpha_first_reached]
        med8 = int(np.median(it8s)) if it8s else None
        med7 = int(np.median(it7s)) if it7s else None
        mean_el = float(np.mean(elapsed_map[c]))
        mode, K = c
        print(f"{mode:>10}  {K:>3}  {hit8:>2}/{ns}  {hit7:>2}/{ns}  "
              f"{best_a:>6}  {best_c:>7.4f}  {mean_c:>7.4f}  "
              f"{str(med8):>10}  {str(med7):>10}  {mean_el:>7.1f}")


if __name__ == "__main__":
    main()
