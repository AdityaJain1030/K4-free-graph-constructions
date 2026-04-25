"""
scripts/run_n23_factorial.py
=============================
N=23 factorial: (operator × basin) 2×2 design.

Runs:
  (3) warm — pure 2-switch, init = SAT frontier graph from graph_db.
  (1) k-fixed — pure 2-switch, init built with target multiset {3:2,4:21}
      (non-uniform cap). Searches the correct multiset basin.
  (mixed) cold — mixed 2-switch + edge-bitvec-flip, spread-cap-1, init =
      uniform random near-regular (d_target=4, mostly {4:23}).
  (mixed-cap2) cold — same mixed operator, spread_cap=2. Conditional
      diagnostic run: interesting only if (1) finds α=6 but (mixed) doesn't.

Reports alpha, c_log, move-kind mix, and k/m trajectory summary.

Frontier reference at N=23:
  c_log = 0.7527, α=6, multiset ∈ {{3:4,4:19} m=44, {3:2,4:21} m=45}.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter

import numpy as np
import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from graph_db.db import DB
from search.switch_tabu import (
    switch_tabu_chain,
    switch_tabu_chain_mixed,
    _random_nearreg_k4free,
    _build_multiset_init,
    SwitchTabuResult,
)

FRONTIER_C = 0.75271
FRONTIER_ALPHA = 6


def _fetch_sat_frontier_adj() -> np.ndarray | None:
    """Pull the SAT-exact non-regular frontier graph at N=23."""
    with DB() as db:
        rows = db.query(n=23, source=["sat_near_regular_nonreg", "server_sat_exact"])
        rows = [r for r in rows if r.get("c_log") is not None]
        rows.sort(key=lambda r: r["c_log"])
        if not rows:
            return None
        G = db.nx(rows[0]["graph_id"])
        return np.array(nx.to_numpy_array(G, dtype=np.uint8)) if G is not None else None


def _k_summary(k_traj: list[int], m_traj: list[int]) -> str:
    """How much of the chain was spent in each (m, k) state?"""
    pairs = list(zip(m_traj, k_traj))
    total = len(pairs)
    counter = Counter(pairs)
    top = counter.most_common(4)
    parts = []
    for (m, k), cnt in top:
        parts.append(f"m={m},k={k}:{cnt}/{total}")
    distinct = len(counter)
    return f"[distinct={distinct}] " + " | ".join(parts)


def _report(label: str, res: SwitchTabuResult, elapsed: float):
    hit = "✓" if res.best_alpha <= FRONTIER_ALPHA else "·"
    gap = res.best_c_log - FRONTIER_C
    degs = res.best_adj.sum(axis=1)
    ms = f"{{{int(degs.min())}:{int((degs == degs.min()).sum())}, {int(degs.max())}:{int((degs == degs.max()).sum())}}}"
    print(f"  {hit} {label:<30} α={res.best_alpha}  c_log={res.best_c_log:.4f}  "
          f"gap={gap:+.4f}  m={int(degs.sum()//2)}  multiset={ms}")
    print(f"    iters={res.n_iters} accepted={res.n_accepted} "
          f"aspiration={res.n_aspiration} ils_restarts={res.n_restarts}  "
          f"moves={dict(res.move_kind_counts)}  elapsed={elapsed:.1f}s")
    print(f"    k/m-trajectory: {_k_summary(res.k_trajectory, res.m_trajectory)}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n_iters", type=int, default=600)
    p.add_argument("--n_restarts_chain", type=int, default=3)
    p.add_argument("--swap_sample", type=int, default=60)
    p.add_argument("--flip_sample", type=int, default=30)
    p.add_argument("--top_k_verify", type=int, default=6)
    p.add_argument("--lb_restarts", type=int, default=12)
    p.add_argument("--tabu_len", type=int, default=14)
    p.add_argument("--patience", type=int, default=60)
    p.add_argument("--perturb_swaps", type=int, default=5)
    p.add_argument("--time_limit_s", type=float, default=90.0)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--run_cap2_regardless", action="store_true",
                   help="Run the spread-cap-2 diagnostic even if unconditional.")
    args = p.parse_args()

    N = 23
    print(f"=== N={N} factorial, frontier c_log={FRONTIER_C:.4f} (α={FRONTIER_ALPHA}) ===")
    print(f"budget: n_iters={args.n_iters}, n_restarts_chain={args.n_restarts_chain}, "
          f"time_limit_s={args.time_limit_s} per chain")
    print()

    rng = np.random.default_rng(args.seed)

    # --- (3) warm: pure 2-switch from SAT frontier ---
    print("--- (3) warm: pure 2-switch from SAT-exact frontier ---")
    warm_adj = _fetch_sat_frontier_adj()
    if warm_adj is None:
        print("  SKIP — no SAT frontier row at N=23.")
        res_warm = None
    else:
        best_warm = None
        for r in range(args.n_restarts_chain):
            rng_chain = np.random.default_rng(args.seed * 1000 + 1 + r)
            t0 = time.monotonic()
            res = switch_tabu_chain(
                warm_adj.copy(),
                n_iters=args.n_iters,
                sample_size=args.swap_sample,
                top_k=args.top_k_verify,
                lb_restarts=args.lb_restarts,
                tabu_len=args.tabu_len,
                patience=args.patience,
                perturb_swaps=args.perturb_swaps,
                rng=rng_chain,
                time_limit_s=args.time_limit_s,
            )
            el = time.monotonic() - t0
            if best_warm is None or res.best_c_log < best_warm[0].best_c_log:
                best_warm = (res, el)
        _report("(3) warm 2-switch", best_warm[0], best_warm[1])
        res_warm = best_warm[0]
    print()

    # --- (1) k-fixed cold: pure 2-switch, init = multiset {3:2, 4:21} ---
    print("--- (1) k-fixed cold: pure 2-switch, multiset-matched init ---")
    target_deg = [3, 3] + [4] * 21
    best_kfix = None
    for r in range(args.n_restarts_chain):
        rng_chain = np.random.default_rng(args.seed * 1000 + 101 + r)
        init = _build_multiset_init(N, target_deg, rng_chain)
        if init is None:
            continue
        t0 = time.monotonic()
        res = switch_tabu_chain(
            init,
            n_iters=args.n_iters,
            sample_size=args.swap_sample,
            top_k=args.top_k_verify,
            lb_restarts=args.lb_restarts,
            tabu_len=args.tabu_len,
            patience=args.patience,
            perturb_swaps=args.perturb_swaps,
            rng=rng_chain,
            time_limit_s=args.time_limit_s,
        )
        el = time.monotonic() - t0
        if best_kfix is None or res.best_c_log < best_kfix[0].best_c_log:
            best_kfix = (res, el)
    if best_kfix is not None:
        _report("(1) k-fixed 2-switch", best_kfix[0], best_kfix[1])
        res_kfix = best_kfix[0]
    else:
        print("  no valid init built")
        res_kfix = None
    print()

    # --- (mixed) cold: mixed 2-switch + edge-flip, spread-cap-1 ---
    print("--- (mixed) cold: 2-switch + edge-bitvec-flip, spread_cap=1 ---")
    best_mix = None
    for r in range(args.n_restarts_chain):
        rng_chain = np.random.default_rng(args.seed * 1000 + 201 + r)
        init = _random_nearreg_k4free(N, 4, rng_chain)
        t0 = time.monotonic()
        res = switch_tabu_chain_mixed(
            init,
            n_iters=args.n_iters,
            sample_size_swap=args.swap_sample,
            sample_size_flip=args.flip_sample,
            top_k=args.top_k_verify,
            lb_restarts=args.lb_restarts,
            tabu_len=args.tabu_len,
            patience=args.patience,
            perturb_swaps=args.perturb_swaps,
            spread_cap=1,
            rng=rng_chain,
            time_limit_s=args.time_limit_s,
        )
        el = time.monotonic() - t0
        if best_mix is None or res.best_c_log < best_mix[0].best_c_log:
            best_mix = (res, el)
    _report("(mixed) cold cap=1", best_mix[0], best_mix[1])
    res_mix = best_mix[0]
    print()

    # --- conditional: spread-cap-2 diagnostic ---
    mix_hit = res_mix.best_alpha <= FRONTIER_ALPHA
    kfix_hit = res_kfix is not None and res_kfix.best_alpha <= FRONTIER_ALPHA
    run_cap2 = args.run_cap2_regardless or (kfix_hit and not mix_hit)
    if run_cap2:
        print("--- (mixed-cap2) cold: spread_cap=2 (conditional diagnostic) ---")
        best_mix2 = None
        for r in range(args.n_restarts_chain):
            rng_chain = np.random.default_rng(args.seed * 1000 + 301 + r)
            init = _random_nearreg_k4free(N, 4, rng_chain)
            t0 = time.monotonic()
            res = switch_tabu_chain_mixed(
                init,
                n_iters=args.n_iters,
                sample_size_swap=args.swap_sample,
                sample_size_flip=args.flip_sample,
                top_k=args.top_k_verify,
                lb_restarts=args.lb_restarts,
                tabu_len=args.tabu_len,
                patience=args.patience,
                perturb_swaps=args.perturb_swaps,
                spread_cap=2,
                rng=rng_chain,
                time_limit_s=args.time_limit_s,
            )
            el = time.monotonic() - t0
            if best_mix2 is None or res.best_c_log < best_mix2[0].best_c_log:
                best_mix2 = (res, el)
        _report("(mixed) cold cap=2", best_mix2[0], best_mix2[1])
    else:
        print("--- (mixed-cap2): skipped (condition not met) ---")
    print()

    # --- 2×2 summary ---
    print("=== 2×2 outcome ===")
    def _cell(r):
        if r is None:
            return "-"
        return f"α={r.best_alpha} c={r.best_c_log:.4f}"
    print(f"                      |  pure 2-switch  |  mixed 2-switch+flip")
    print(f"  correct basin (warm)|  {_cell(res_warm):<15}  |  -")
    print(f"  correct basin (k=2) |  {_cell(res_kfix):<15}  |  -")
    print(f"  cold (k=0 init)     |  -              |  {_cell(res_mix):<15}")
    print(f"  frontier            |  α=6 c={FRONTIER_C:.4f}")


if __name__ == "__main__":
    main()
