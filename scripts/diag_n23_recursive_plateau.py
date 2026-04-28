"""
scripts/diag_n23_recursive_plateau.py
======================================
Recursive plateau diagnostic at α=7: reach an α=7 state via the
composite-K=6 tabu, then enumerate all feasible 2-switches, exact-α
each, cross-tab with α_lb.

Question: does the α=7 → α=6 transition have the same 100%-recall /
low-precision surrogate structure as α=9 → α=8, or does something
fundamentally change between α=7 and α=6?
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.stochastic_walk.switch_tabu import (
    switch_tabu_chain, _build_multiset_init, _try_switch, _edges_of,
)
from utils.graph_props import alpha_bb_clique_cover
from utils.alpha_surrogate import alpha_lb


def enumerate_feasible_switches(adj: np.ndarray):
    edges = _edges_of(adj)
    for i in range(len(edges)):
        a, b = edges[i]
        for j in range(i + 1, len(edges)):
            c, d = edges[j]
            for rw in ("ac_bd", "ad_bc"):
                aa, bb, cc, dd = a, b, c, d
                if rw == "ad_bc":
                    cc, dd = dd, cc
                new = _try_switch(adj, aa, bb, cc, dd)
                if new is not None:
                    yield new


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--lb_restarts", type=int, default=16)
    p.add_argument("--n_iters", type=int, default=1500)
    p.add_argument("--target_alpha", type=int, default=7)
    args = p.parse_args()

    N = 23
    target = [3, 3] + [4] * 21

    rng = np.random.default_rng(args.seed)
    init = _build_multiset_init(N, target, rng)
    assert init is not None
    print(f"init: α={alpha_bb_clique_cover(init)[0]}")

    # Run composite K=6 chain to reach α=target_alpha.
    print(f"running composite K=6 until α<={args.target_alpha}...")
    t0 = time.monotonic()
    res = switch_tabu_chain(
        init, n_iters=args.n_iters, sample_size=60, top_k=6,
        lb_restarts=12, tabu_len=14, patience=60, perturb_swaps=5,
        rng=rng, time_limit_s=120, use_exact_score=False,
        composite_score=True,
    )
    el = time.monotonic() - t0
    print(f"reached α={res.best_alpha} in {res.n_iters} iters ({el:.1f}s).  "
          f"alpha_first_reached={res.alpha_first_reached}")

    if res.best_alpha > args.target_alpha:
        print(f"FAILED to reach α={args.target_alpha}. Stopping.")
        return

    base = res.best_adj
    a_base, _ = alpha_bb_clique_cover(base)
    degs = base.sum(axis=1)
    m = int(base.sum() // 2)
    print(f"\nenumerating 2-switches from α={a_base} state "
          f"(m={m}, d=[{int(degs.min())},{int(degs.max())}])...")

    t0 = time.monotonic()
    exact_a = []
    lb_a = []
    for new in enumerate_feasible_switches(base):
        exact_a.append(alpha_bb_clique_cover(new)[0])
        lb_a.append(alpha_lb(new, restarts=args.lb_restarts, rng=rng))
    n_switches = len(exact_a)
    el = time.monotonic() - t0
    print(f"enumerated {n_switches} 2-switches in {el:.1f}s\n")

    c_ex = Counter(exact_a)
    print(f"exact-α distribution (resulting graphs):")
    for a in sorted(c_ex):
        pct = 100 * c_ex[a] / n_switches
        marker = "  ← IMPROVERS" if a < a_base else ("" if a == a_base else "  (worse)")
        print(f"  α={a}: {c_ex[a]:>5}  ({pct:5.1f}%){marker}")

    c_lb = Counter(lb_a)
    print(f"\nα_lb distribution:")
    for a in sorted(c_lb):
        pct = 100 * c_lb[a] / n_switches
        print(f"  α_lb={a}: {c_lb[a]:>5}  ({pct:5.1f}%)")

    # Cross-tab
    pairs = list(zip(exact_a, lb_a))
    ex_vals = sorted(set(exact_a))
    lb_vals = sorted(set(lb_a))
    print("\ncross-tab (rows = exact α, cols = α_lb):")
    print(f"  {'ex\\lb':>6}", *(f"{v:>6}" for v in lb_vals))
    for ex in ex_vals:
        row = Counter(lb for x, lb in pairs if x == ex)
        cells = [f"{row.get(v, 0):>6}" for v in lb_vals]
        marker = "  ← IMPROVERS" if ex < a_base else ""
        print(f"  {ex:>6}", *cells, marker)

    # surrogate recall / precision on improvers
    improvers = [i for i, a in enumerate(exact_a) if a < a_base]
    n_imp = len(improvers)
    if n_imp == 0:
        print(f"\nNO IMPROVERS exist from this α={a_base} state.")
        print(f"  → 2-switch cannot reach α<{a_base} from here in one hop.")
        print(f"  → any descent to α<{a_base} requires plateau walk to a different α={a_base} state.")
    else:
        lb_values_of_improvers = [lb_a[i] for i in improvers]
        min_lb_in_pool = min(lb_a)
        imp_with_min_lb = sum(1 for i in improvers if lb_a[i] == min_lb_in_pool)
        total_at_min_lb = sum(1 for v in lb_a if v == min_lb_in_pool)
        print(f"\nimprover analysis:")
        print(f"  improvers: {n_imp}/{n_switches} = {100*n_imp/n_switches:.2f}%")
        print(f"  α_lb values of improvers: {sorted(set(lb_values_of_improvers))}")
        print(f"  min α_lb in pool: {min_lb_in_pool}")
        print(f"  improvers with α_lb=min: {imp_with_min_lb}/{total_at_min_lb}  "
              f"(precision at min-α_lb tier = {100*imp_with_min_lb/max(1,total_at_min_lb):.1f}%)")
        # Top-K precision at various K
        sort_idx = np.argsort(lb_a)
        for topK in [6, 20, 60, 100]:
            if topK > n_switches:
                break
            top = sort_idx[:topK]
            in_imp = sum(1 for i in top if exact_a[i] < a_base)
            print(f"  top-{topK} by α_lb: {in_imp}/{topK} improvers "
                  f"({100*in_imp/topK:.1f}%)   uniform baseline = "
                  f"{100*n_imp/n_switches:.2f}%")


if __name__ == "__main__":
    main()
