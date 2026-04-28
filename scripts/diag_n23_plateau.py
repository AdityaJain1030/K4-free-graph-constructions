"""
scripts/diag_n23_plateau.py
============================
Enumerate every feasible 2-switch from a multiset-matched N=23 init
(m=45, k=2), compute exact α of every resulting graph, report the
distribution.

If the histogram is dominated by one value (α=8), the plateau
hypothesis is confirmed: within-multiset α-landscape is flat, and
any pure-α ranker can only pick tie-break moves. If it's a smooth
spread, something else is driving the (1) cell's miss.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.stochastic_walk.switch_tabu import _build_multiset_init, _try_switch, _edges_of
from utils.graph_props import alpha_bb_clique_cover, find_k4
from utils.alpha_surrogate import alpha_lb


def enumerate_feasible_switches(adj: np.ndarray):
    """Yield (new_adj, (a,b), (c,d), rewiring) for every K4-free 2-switch."""
    edges = _edges_of(adj)
    m = len(edges)
    for i in range(m):
        a, b = edges[i]
        for j in range(i + 1, m):
            c, d = edges[j]
            for rewiring in ("ac_bd", "ad_bc"):
                aa, bb, cc, dd = a, b, c, d
                if rewiring == "ad_bc":
                    cc, dd = dd, cc
                new = _try_switch(adj, aa, bb, cc, dd)
                if new is not None:
                    yield new, (aa, bb), (cc, dd), rewiring


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--lb_restarts", type=int, default=16)
    args = p.parse_args()

    N = 23
    target = [3, 3] + [4] * 21  # (m=45, k=2)
    rng = np.random.default_rng(args.seed)
    init = _build_multiset_init(N, target, rng)
    assert init is not None
    a_init, _ = alpha_bb_clique_cover(init)
    degs = init.sum(axis=1)
    m_init = int(init.sum() // 2)
    print(f"init state: m={m_init} d=[{int(degs.min())},{int(degs.max())}] α={a_init}")

    t0 = time.monotonic()
    exact_alphas = []
    lb_alphas = []
    for k, (new, _, _, _) in enumerate(enumerate_feasible_switches(init)):
        a_ex, _ = alpha_bb_clique_cover(new)
        exact_alphas.append(a_ex)
        a_lb = alpha_lb(new, restarts=args.lb_restarts, rng=rng)
        lb_alphas.append(a_lb)
    elapsed = time.monotonic() - t0
    n_switches = len(exact_alphas)

    print(f"enumerated {n_switches} feasible K4-free 2-switches in {elapsed:.1f}s")
    print()
    print("exact-α distribution of resulting graphs:")
    c_exact = Counter(exact_alphas)
    for a in sorted(c_exact):
        pct = 100 * c_exact[a] / n_switches
        print(f"  α={a}: {c_exact[a]:>5}  ({pct:5.1f}%)")
    print()
    print("α_lb (surrogate) distribution (same graphs):")
    c_lb = Counter(lb_alphas)
    for a in sorted(c_lb):
        pct = 100 * c_lb[a] / n_switches
        print(f"  α_lb={a}: {c_lb[a]:>5}  ({pct:5.1f}%)")
    print()

    # Cross-tab: given exact α=X, what α_lb values does the surrogate report?
    # The "does surrogate break ties usefully?" question lives here.
    print("cross-tab  (rows = exact α, cols = α_lb count)  — on-plateau rows matter:")
    pairs = list(zip(exact_alphas, lb_alphas))
    ex_vals = sorted(set(exact_alphas))
    lb_vals = sorted(set(lb_alphas))
    print(f"  {'ex\\lb':>6}", *(f"{v:>6}" for v in lb_vals))
    for ex in ex_vals:
        row = Counter(lb for x, lb in pairs if x == ex)
        cells = [f"{row.get(v, 0):>6}" for v in lb_vals]
        print(f"  {ex:>6}", *cells)

    # If the plateau dominates, what fraction of plateau moves does the
    # surrogate rank above/below the rare non-plateau moves?
    if ex_vals:
        plateau = max(c_exact, key=c_exact.get)  # mode
        non_plateau = [lb for x, lb in pairs if x != plateau]
        on_plateau = [lb for x, lb in pairs if x == plateau]
        if non_plateau:
            print()
            print(f"Non-plateau α≠{plateau}: n={len(non_plateau)}, "
                  f"mean α_lb={np.mean(non_plateau):.2f}")
            print(f"On-plateau  α={plateau} : n={len(on_plateau)}, "
                  f"mean α_lb={np.mean(on_plateau):.2f}")
            # Among the lowest surrogate α_lb swaps, what fraction are
            # improving (exact α < plateau)?
            sort_idx = np.argsort(lb_alphas)
            for topK in [5, 10, 20, 50, 100]:
                if topK > n_switches:
                    break
                top = sort_idx[:topK]
                improvs = sum(1 for i in top if exact_alphas[i] < plateau)
                print(f"  top-{topK} by α_lb: {improvs}/{topK} actually-improving "
                      f"({100*improvs/topK:.0f}%)  expected_uniform="
                      f"{100*len(non_plateau)/n_switches:.2f}%")


if __name__ == "__main__":
    main()
