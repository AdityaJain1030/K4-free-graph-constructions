"""
experiments/edge_gradients/run_globality.py
===========================================
Test whether the SDP θ dual at t=0 (on the α-flat saddle G_0) predicts
which edges end up being α-critical in G_T (after T greedy edge
additions and α has dropped).

If the SDP dual is "globally" attributing — i.e. its t=0 ranking already
identifies the edges that will eventually do α-blocking work — then it
isn't just a locally-good signal; it's the actual RL credit-assignment
property: a tight per-edge α gradient that survives multi-step rollout.

Procedure per saddle G_0:
  1. Compute SDP X_uw at t=0 for every K4-free-safe non-edge.
  2. Run SDP greedy for T steps → G_T.
  3. For each added edge e ∈ E(G_T) \\ E(G_0), compute drop-α at G_T:
        drop_T(e) = α(G_T - e) - α(G_T)        (≥ 0; > 0 means α-critical)
  4. Spearman correlation of  (X_uw at t=0)  vs  (drop_T)  over added edges.

We report:
  - Spearman ρ per saddle (and aggregate stats).
  - Number of α-critical added edges (drop_T > 0).
  - The X_uw rank at t=0 of the most-α-critical added edge.

Comparison rows: same metric for hardcore_comarg, drop_alpha (where
applicable), random — to isolate whether SDP's t=0 lookahead is unique
or whether all saddle-escaping methods share it.
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import statistics
import sys
import time

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from utils.graph_props import alpha_bb_clique_cover_nx as alpha_nx  # noqa: E402
from nonedge_methods import METHODS, safe_non_edges  # noqa: E402
from run_followpath import find_saddles  # noqa: E402


def spearman(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    rx = _ranks(xs)
    ry = _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx)
    dy = sum((b - my) ** 2 for b in ry)
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy) ** 0.5


def _ranks(xs):
    pairs = sorted(enumerate(xs), key=lambda p: p[1])
    rank = [0.0] * len(xs)
    i = 0
    while i < len(pairs):
        j = i
        while j + 1 < len(pairs) and pairs[j + 1][1] == pairs[i][1]:
            j += 1
        avg = 0.5 * (i + j) + 1
        for k in range(i, j + 1):
            rank[pairs[k][0]] = avg
        i = j + 1
    return rank


def trajectory_with_score_at_t0(G0, method_name, T, rng, score_at_t0):
    """
    Greedy add T edges using `method_name`. Return (G_T, added_edges,
    method_score_at_t0) where method_score_at_t0 is the score the method
    assigned at t=0 — which we keep for downstream Spearman.
    """
    G = G0.copy()
    added: list[tuple[int, int]] = []
    fn = METHODS[method_name]
    for _ in range(T):
        sne = safe_non_edges(G)
        if not sne:
            break
        if method_name == "random":
            scores = fn(G, sne, rng=rng)
        else:
            scores = fn(G, sne)
        if scores is None:
            return G, added
        max_s = max(scores.values())
        cands = [e for e, s in scores.items() if s >= max_s - 1e-9]
        chosen = rng.choice(cands)
        added.append(tuple(sorted(chosen)))
        G.add_edge(*chosen)
    return G, added


def compute_drop_alpha_at(G, edges):
    """drop-α(G, e) for each e ∈ edges."""
    base, _ = alpha_nx(G)
    out = {}
    for e in edges:
        H = G.copy()
        H.remove_edge(*e)
        a, _ = alpha_nx(H)
        out[e] = a - base
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--seeds", type=int, default=15)
    ap.add_argument("--steps", type=int, default=20)
    ap.add_argument("--density", type=float, default=0.30)
    ap.add_argument("--rng-seed", type=int, default=42)
    ap.add_argument("--out", default=os.path.join(HERE, "globality_results.csv"))
    args = ap.parse_args()

    print(f"[globality] hunting α-flat saddles N={args.n}", flush=True)
    rng = random.Random(args.rng_seed)
    saddles = find_saddles(args.n, args.seeds, args.density, rng)
    print(f"[globality] {len(saddles)} starting graphs in hand\n", flush=True)

    # Precompute at t=0 the four method scores we want as predictors.
    PREDICTORS = ["sdp_X_uw", "hardcore_comarg", "drop_e_max", "random"]
    rows = []
    for sidx, (G0, a0, _, _) in enumerate(saddles):
        print(f"[saddle {sidx}] α0={a0}, |E|={G0.number_of_edges()}, "
              f"safe non-edges={len(safe_non_edges(G0))}", flush=True)
        sne0 = safe_non_edges(G0)

        # Predictor scores at t=0
        score_at_0 = {}
        for method in PREDICTORS:
            s = METHODS[method](G0, sne0, rng=random.Random(sidx)) \
                if method == "random" else METHODS[method](G0, sne0)
            score_at_0[method] = s

        # Run SDP greedy → G_T
        traj_rng = random.Random(args.rng_seed * 100 + sidx)
        t0 = time.time()
        G_T, added = trajectory_with_score_at_t0(
            G0, "sdp_X_uw", args.steps, traj_rng, score_at_0["sdp_X_uw"])
        a_T, _ = alpha_nx(G_T)
        print(f"  SDP greedy: α0={a0} → α_T={a_T} ({a0-a_T} drop), "
              f"added={len(added)} edges  ({time.time()-t0:.1f}s)", flush=True)

        # drop-α on added edges in G_T
        drop_T = compute_drop_alpha_at(G_T, added)
        n_critical = sum(1 for d in drop_T.values() if d > 0)
        print(f"  α-critical added edges (drop_α > 0 at G_T): "
              f"{n_critical}/{len(added)}", flush=True)

        # For each predictor, compute Spearman between predictor-at-t=0
        # and drop_T over the added edges.
        for method in PREDICTORS:
            s0 = score_at_0[method]
            if s0 is None:
                rows.append(dict(saddle=sidx, predictor=method,
                                 spearman=None, n_added=len(added),
                                 n_critical=n_critical, alpha_drop=a0 - a_T,
                                 reason="predictor unavailable"))
                continue
            xs = [s0.get(e, 0.0) for e in added]
            ys = [drop_T[e] for e in added]
            rho = spearman(xs, ys)
            # Also: did the predictor's top-pick at t=0 end up α-critical?
            top_e = max(s0.items(), key=lambda kv: kv[1])[0]
            top_in_added = top_e in added
            top_critical = (top_in_added and drop_T.get(top_e, 0) > 0)
            rows.append(dict(saddle=sidx, predictor=method,
                             spearman=round(rho, 4) if rho is not None else None,
                             n_added=len(added), n_critical=n_critical,
                             alpha_drop=a0 - a_T,
                             top_in_added=int(top_in_added),
                             top_critical=int(top_critical),
                             reason=""))
            print(f"    {method:18s} spearman(t=0 vs drop_T) = "
                  f"{rho if rho is None else round(rho, 3)}   "
                  f"top@t=0 in added: {top_in_added}   "
                  f"top@t=0 α-critical at T: {top_critical}",
                  flush=True)
        print()

    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"[globality] wrote {args.out}")

    # Aggregate
    print()
    print("Aggregate Spearman(predictor at t=0  vs  drop-α at T)")
    by = {p: [] for p in PREDICTORS}
    top_added = {p: 0 for p in PREDICTORS}
    top_crit = {p: 0 for p in PREDICTORS}
    n = 0
    for r in rows:
        if r["spearman"] is None:
            continue
        by[r["predictor"]].append(float(r["spearman"]))
        if r.get("top_in_added"):
            top_added[r["predictor"]] += int(r["top_in_added"])
        if r.get("top_critical"):
            top_crit[r["predictor"]] += int(r["top_critical"])
    n = max(len([r for r in rows if r["predictor"] == p and r["spearman"] is not None])
            for p in PREDICTORS)
    print(f"  predictor          n      mean_ρ   median_ρ   min_ρ   max_ρ   top_in_added  top_α_critical")
    for p in PREDICTORS:
        rs = by[p]
        if not rs:
            print(f"  {p:18s} -")
            continue
        print(f"  {p:18s} {len(rs):2d}    {statistics.mean(rs):+.3f}    "
              f"{statistics.median(rs):+.3f}    {min(rs):+.3f}    {max(rs):+.3f}    "
              f"{top_added[p]:2d}/{n:2d}         {top_crit[p]:2d}/{n:2d}")


if __name__ == "__main__":
    main()
