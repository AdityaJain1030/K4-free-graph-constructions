#!/usr/bin/env python3
"""
scripts/paley_randomized_blowup.py
===================================
Randomized blow-up experiment on Paley(17).

For k=2 (so n = 34) and each Paley(17) edge uv, replace the standard
K_{2,2} bipartite between fiber_u and fiber_v with a random 2×2
bipartite graph where each of the 4 possible edges is independently
present with probability p. Fibers remain internally empty (no edges
inside any fiber).

  Standard Cayley blow-up: α = k · α(P17) = 2 · 3 = 6 exactly.
  Randomized blow-up:      α = ?  — experiment asks whether any random
                                    trial achieves α < 6.

For each p ∈ {0.2, 0.3, 0.4, 0.5} run 1000 trials, compute exact α,
and record summary + the K₄-free survivors whose α is < 6 (if any).

Results:
  * graphs/paley_randomized_blowup.json — K₄-free graphs with α<6
    (if we find any), plus the fixed baseline standard blow-up.
  * Console summary per p: count K4-free, (min, max, mean, median) α.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
import time

import numpy as np
import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS, DB
from utils.graph_props import alpha_exact as alpha_exact_np, is_k4_free_nx


# ---------------------------------------------------------------------------


def paley17() -> nx.Graph:
    """Paley(17) = Cay(Z_17, squares)."""
    q = 17
    sq = {pow(i, 2, q) for i in range(1, q)}
    G = nx.Graph()
    G.add_nodes_from(range(q))
    for u in range(q):
        for s in sq:
            v = (u + s) % q
            if u < v:
                G.add_edge(u, v)
    return G


def random_blowup(G_base: nx.Graph, k: int, p: float,
                  rng: np.random.Generator) -> nx.Graph:
    """
    Blow-up with random 2×2 bipartites per edge. fiber_u = {u*k, u*k+1, ..., u*k+k-1}.
    For each uv ∈ E(G_base) and each (i, j) ∈ [k]×[k], include edge iid with
    probability p.
    """
    n = G_base.number_of_nodes() * k
    B = nx.Graph()
    B.add_nodes_from(range(n))
    for u, v in G_base.edges():
        # k×k edge draws
        mask = rng.random((k, k)) < p
        for i in range(k):
            for j in range(k):
                if mask[i, j]:
                    B.add_edge(u * k + i, v * k + j)
    return B


def alpha_exact_fast(G: nx.Graph) -> int:
    adj = np.asarray(nx.to_numpy_array(G, dtype=np.uint8))
    a, _mis = alpha_exact_np(adj)
    return int(a)


# ---------------------------------------------------------------------------


def run_experiment(n_trials: int, ps, k: int, seed: int, save_below: int):
    rng = np.random.default_rng(seed)
    P17 = paley17()

    # Standard blow-up baseline (p=1.0)
    std = random_blowup(P17, k=k, p=1.0, rng=rng)
    std_alpha = alpha_exact_fast(std)
    std_k4 = is_k4_free_nx(std)
    print(f"[baseline k={k}] standard blow-up: n={std.number_of_nodes()} "
          f"m={std.number_of_edges()} α={std_alpha} K4-free={std_k4}", flush=True)

    store = GraphStore(DEFAULT_GRAPHS)
    hits = []
    all_rows = []

    for p in ps:
        print(f"\n=== p = {p}, trials = {n_trials} ===", flush=True)
        t0 = time.monotonic()
        alphas = []
        k4_count = 0
        below_count = 0
        for trial in range(n_trials):
            B = random_blowup(P17, k=k, p=p, rng=rng)
            if not is_k4_free_nx(B):
                continue
            k4_count += 1
            a = alpha_exact_fast(B)
            alphas.append(a)
            if a < save_below:
                below_count += 1
                # save one graph per (p, a) for inspection
                hits.append(dict(
                    graph=B, p=p, trial=trial, alpha=a,
                    n=B.number_of_nodes(), m=B.number_of_edges(),
                ))
            if (trial + 1) % max(1, n_trials // 10) == 0:
                elapsed = time.monotonic() - t0
                print(f"  trial {trial+1:>4}/{n_trials}  "
                      f"K4_free_so_far={k4_count} α≥6_so_far={k4_count - below_count}  "
                      f"(t={elapsed:.1f}s)",
                      flush=True)

        dt = time.monotonic() - t0
        if alphas:
            row = dict(
                p=p, n_trials=n_trials, k4_free=k4_count,
                alpha_min=min(alphas), alpha_max=max(alphas),
                alpha_mean=statistics.mean(alphas),
                alpha_median=statistics.median(alphas),
                below_save=below_count,
                elapsed_s=round(dt, 2),
            )
        else:
            row = dict(
                p=p, n_trials=n_trials, k4_free=0,
                alpha_min=None, alpha_max=None, alpha_mean=None,
                alpha_median=None, below_save=0, elapsed_s=round(dt, 2),
            )
        all_rows.append(row)
        print(f"  p={p}  K4-free={k4_count}/{n_trials}  "
              f"α range {row['alpha_min']}..{row['alpha_max']}  "
              f"mean {row['alpha_mean']}  median {row['alpha_median']}  "
              f"α<{save_below}: {row['below_save']}  "
              f"({dt:.1f}s)", flush=True)

    # Summary
    print("\n" + "=" * 78)
    print(f"{'p':>5}{'trials':>8}{'K4-free':>9}{'α_min':>7}{'α_max':>7}"
          f"{'mean':>9}{'med':>7}{'α<{save_below}':>10}")
    print("=" * 78)
    for r in all_rows:
        print(f"{r['p']:>5}{r['n_trials']:>8}{r['k4_free']:>9}"
              f"{str(r['alpha_min']):>7}{str(r['alpha_max']):>7}"
              f"{str(round(r['alpha_mean'],2)) if r['alpha_mean'] else '—':>9}"
              f"{str(r['alpha_median']):>7}{r['below_save']:>10}")

    # Save hits + baseline
    print("\nIngesting into graph_db under source='paley_randomized_blowup'...", flush=True)
    # always save the baseline, tagged
    gid, was_new = store.add_graph(
        std, source="paley_randomized_blowup",
        filename="paley_randomized_blowup.json",
        construction="standard_K22_blowup",
        p=1.0,
        k=k,
        baseline=True,
        alpha_exact=int(std_alpha),
    )
    print(f"  [baseline {'new' if was_new else 'dup'}] {gid[:12]}", flush=True)

    for h in hits:
        gid, was_new = store.add_graph(
            h['graph'], source="paley_randomized_blowup",
            filename="paley_randomized_blowup.json",
            construction="random_bipartite_blowup",
            p=float(h['p']),
            k=k,
            trial=int(h['trial']),
            alpha_exact=int(h['alpha']),
            baseline=False,
        )
        print(f"  [hit p={h['p']} α={h['alpha']} {'new' if was_new else 'dup'}] "
              f"{gid[:12]}", flush=True)

    # Sync
    with DB() as db:
        db.sync(source="paley_randomized_blowup", verbose=True)

    return all_rows, hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-trials", type=int, default=1000)
    ap.add_argument("--ps", type=float, nargs="+", default=[0.2, 0.3, 0.4, 0.5])
    ap.add_argument("--k", type=int, default=2)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--save-below", type=int, default=6,
                    help="Save any trial whose α is strictly less than this.")
    args = ap.parse_args()

    run_experiment(args.n_trials, args.ps, args.k, args.seed, args.save_below)
    return 0


if __name__ == "__main__":
    sys.exit(main())
