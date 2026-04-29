"""
experiments/edge_gradients/run_followpath.py
============================================
Saddle-escape gradient-following test (variant C).

For each starting graph G_0 chosen so that *no single-edge addition*
lowers α(G_0) — i.e. drop-α-additive is identically zero at step 1 —
each method greedily adds T edges (one per step), choosing the
highest-scored K4-free-safe non-edge. We track α(G_t) and report:

  - α_drop(t)        = α(G_0) - α(G_t)  (cumulative drop, ≥ 0)
  - first_drop_t     = step at which α first decreases (None if never)
  - wasted_steps     = #t where α(G_t) = α(G_{t-1})
  - per-step wall time

Methods compared (all in nonedge_methods.METHODS):
  random, drop_alpha, drop_e_max, drop_l_hc,
  hardcore_comarg, sdp_X_uw, lp_xu_plus_xw, hoffman_grad

CLI:
  --n          target N for starting graphs (default 20)
  --seeds      number of saddle starting graphs (default 15)
  --steps      T (default 20)
  --density    rough |E| / (N choose 2) for random K4-free seed (default 0.30)
"""
from __future__ import annotations

import argparse
import csv
import itertools
import os
import random
import sys
import time

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from utils.graph_props import alpha_bb_clique_cover_nx as alpha_nx, is_k4_free  # noqa: E402
from nonedge_methods import METHODS, safe_non_edges  # noqa: E402


# ---------------------------------------------------------------------------
# Saddle-graph generation
# ---------------------------------------------------------------------------

def random_k4free(n: int, target_edges: int, rng: random.Random) -> nx.Graph:
    """Add random edges, skipping K4-creating ones, until target_edges or stuck."""
    G = nx.empty_graph(n)
    pairs = list(itertools.combinations(range(n), 2))
    rng.shuffle(pairs)
    for u, v in pairs:
        if G.number_of_edges() >= target_edges:
            break
        G.add_edge(u, v)
        A = nx.to_numpy_array(G, dtype=np.uint8)
        if not is_k4_free(A):
            G.remove_edge(u, v)
    return G


def is_alpha_flat(G: nx.Graph) -> bool:
    """No single safe edge addition lowers α."""
    base, _ = alpha_nx(G)
    for e in safe_non_edges(G):
        H = G.copy()
        H.add_edge(*e)
        if alpha_nx(H)[0] < base:
            return False
    return True


def has_two_step_drop(G: nx.Graph, rng: random.Random, probes: int = 30) -> bool:
    """Heuristic: try random pairs of safe non-edges; any pair lowering α?"""
    base, _ = alpha_nx(G)
    sne = safe_non_edges(G)
    if len(sne) < 2:
        return False
    pairs = list(itertools.combinations(sne, 2))
    rng.shuffle(pairs)
    for (e1, e2) in pairs[:probes]:
        H = G.copy()
        H.add_edge(*e1)
        if not is_k4_free(nx.to_numpy_array(H, dtype=np.uint8)):
            continue
        H.add_edge(*e2)
        if not is_k4_free(nx.to_numpy_array(H, dtype=np.uint8)):
            continue
        if alpha_nx(H)[0] < base:
            return True
    return False


def find_saddles(n: int, n_seeds: int, density: float,
                 rng: random.Random, max_attempts: int = 500):
    """Sample random K4-free graphs until n_seeds α-flat-with-2-step-drop are found."""
    target_edges = int(round(density * n * (n - 1) / 2))
    saddles = []
    attempts = 0
    while len(saddles) < n_seeds and attempts < max_attempts:
        attempts += 1
        G = random_k4free(n, target_edges, rng)
        if G.number_of_edges() < 5:
            continue
        if not is_alpha_flat(G):
            continue
        if not has_two_step_drop(G, rng, probes=40):
            continue
        a, _ = alpha_nx(G)
        saddles.append((G, a, target_edges, attempts))
        print(f"  saddle {len(saddles)}/{n_seeds}: |V|={n}, |E|={G.number_of_edges()}, "
              f"α={a}, found after {attempts} samples", flush=True)
    return saddles


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------

def trajectory(G0: nx.Graph, method: str, T: int, rng: random.Random):
    """Run T greedy add steps using method. Returns dict with α(t), wall times, choices."""
    G = G0.copy()
    a0, _ = alpha_nx(G)
    alphas = [a0]
    times = []
    choices = []
    for t in range(T):
        sne = safe_non_edges(G)
        if not sne:
            break
        t0 = time.time()
        scores = METHODS[method](G, sne, rng=rng) if method == "random" else METHODS[method](G, sne)
        if scores is None:
            return dict(alphas=alphas, times=times, choices=choices,
                        skipped=True)
        # break ties uniformly at random
        max_s = max(scores.values())
        cands = [e for e, s in scores.items() if s >= max_s - 1e-9]
        chosen = rng.choice(cands)
        dt = time.time() - t0
        G.add_edge(*chosen)
        a, _ = alpha_nx(G)
        alphas.append(a)
        times.append(round(dt, 4))
        choices.append(chosen)
    return dict(alphas=alphas, times=times, choices=choices, skipped=False)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seeds", type=int, default=15)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--density", type=float, default=0.30)
    ap.add_argument("--rng-seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(HERE, "followpath_results.csv"))
    ap.add_argument("--summary", default=os.path.join(HERE, "followpath_summary.csv"))
    args = ap.parse_args()

    print(f"[followpath] hunting α-flat saddles at N={args.n} density={args.density}", flush=True)
    rng = random.Random(args.rng_seed)
    saddles = find_saddles(args.n, args.seeds, args.density, rng)
    print(f"[followpath] {len(saddles)} starting graphs in hand", flush=True)

    rows = []
    summary = []
    method_names = list(METHODS.keys())

    for sidx, (G0, a0, m_target, n_attempts) in enumerate(saddles):
        for method in method_names:
            traj_rng = random.Random(args.rng_seed * 100 + sidx)
            t_start = time.time()
            r = trajectory(G0, method, args.steps, traj_rng)
            wall = time.time() - t_start
            alphas = r["alphas"]
            for t, a in enumerate(alphas):
                rows.append(dict(
                    saddle=sidx, method=method, t=t,
                    alpha=a, alpha_drop=a0 - a,
                    n=args.n, m0=G0.number_of_edges(),
                    skipped=int(r["skipped"]),
                ))
            # summary
            first_drop = next((t for t, a in enumerate(alphas) if a < a0), None)
            wasted = sum(1 for i in range(1, len(alphas)) if alphas[i] == alphas[i - 1])
            summary.append(dict(
                saddle=sidx, method=method, n=args.n,
                a0=a0, alpha_final=alphas[-1],
                alpha_drop=a0 - alphas[-1],
                steps_taken=len(alphas) - 1,
                first_drop_t=first_drop,
                wasted_steps=wasted,
                wall_s=round(wall, 3),
                skipped=int(r["skipped"]),
            ))
            tag = "SKIP" if r["skipped"] else f"α0={a0} → α_T={alphas[-1]}"
            print(f"  saddle{sidx:2d}  {method:18s}  {tag}  "
                  f"first_drop={first_drop}  wasted={wasted}  ({wall:.1f}s)",
                  flush=True)

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); [w.writerow(r) for r in rows]
    with open(args.summary, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0].keys()))
        w.writeheader(); [w.writerow(r) for r in summary]
    print(f"[followpath] wrote {args.out} ({len(rows)} rows) and {args.summary}")


if __name__ == "__main__":
    main()
