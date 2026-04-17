#!/usr/bin/env python3
"""
Selective Cross-Edge Experiment for K₄-Free Graphs
====================================================
Tests whether selective (non-complete-bipartite) cross-edges between
graph blocks can close the gap to SAT-optimal c values.

Depth ablation: from 2 blocks (depth 1) to N individual vertices (raw edges).
Three strategies: random, degree_balance, alpha_stop.

Usage
-----
  micromamba run -n funsearch python experiments/selective_crossedge/run_experiment.py
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

# Import core functions from block_decomposition
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "block_decomposition"))
from run_experiment import (
    alpha_exact,
    alpha_sat,
    is_k4_free,
    graph6_to_adj,
    adj_to_graph6,
    compute_c_value,
)

sys.stdout.reconfigure(line_buffering=True)

OUTDIR = os.path.dirname(os.path.abspath(__file__))
PLOT_DIR = os.path.join(OUTDIR, "plots")
LIBRARY_PATH = os.path.join(
    os.path.dirname(__file__), "..", "block_decomposition", "library.json"
)
PARETO_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "SAT", "k4free_ilp", "results")
)


# ============================================================================
# Load data
# ============================================================================

def load_library():
    """Load the block library from JSON."""
    with open(LIBRARY_PATH) as f:
        data = json.load(f)
    lib = data if isinstance(data, list) else data.get("blocks", data.get("library", []))
    print(f"  Loaded {len(lib)} blocks from library")
    return lib


def load_sat_optimal(N):
    """Load SAT-optimal pareto data for a given N."""
    path = os.path.join(PARETO_DIR, f"pareto_n{N}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        data = json.load(f)
    frontier = data.get("pareto_frontier", [])
    if not frontier:
        return None
    frontier = [e for e in frontier if e.get("c_log") is not None]
    if not frontier:
        return None
    best = min(frontier, key=lambda e: e["c_log"])
    return {
        "alpha": best["alpha"],
        "d_max": best["d_max"],
        "c": best["c_log"],
        "edges": len(best.get("edges", [])),
    }


def select_block_from_library(library, n, rng):
    """Select a random block of size n from the library.
    For n <= 2, return a manual block. For n >= 3, pick from library."""
    if n == 1:
        return np.zeros((1, 1), dtype=np.bool_)
    if n == 2:
        # K2 is K4-free, alpha=1, d_max=1
        adj = np.zeros((2, 2), dtype=np.bool_)
        adj[0, 1] = adj[1, 0] = True
        return adj

    candidates = [b for b in library if b["n"] == n]
    if not candidates:
        # Fallback: empty graph on n vertices
        return np.zeros((n, n), dtype=np.bool_)

    block = rng.choice(candidates)
    adj = np.zeros((n, n), dtype=np.bool_)
    for u, v in block["edges"]:
        adj[u, v] = adj[v, u] = True
    return adj


# ============================================================================
# Core composition functions
# ============================================================================

def build_disjoint_union(blocks):
    """Build disjoint union adjacency matrix from list of block adj matrices."""
    n_total = sum(b.shape[0] for b in blocks)
    adj = np.zeros((n_total, n_total), dtype=np.bool_)
    offset = 0
    for b in blocks:
        nb = b.shape[0]
        adj[offset:offset + nb, offset:offset + nb] = b
        offset += nb
    return adj


def get_block_membership(block_sizes):
    """Return array mapping vertex -> block index."""
    membership = np.zeros(sum(block_sizes), dtype=np.int32)
    offset = 0
    for idx, s in enumerate(block_sizes):
        membership[offset:offset + s] = idx
        offset += s
    return membership


def would_create_k4(adj, nbr_masks, u, v):
    """Incremental K4 check: would adding edge (u,v) create a K4?
    A K4 is created iff there exist two common neighbors c,d of both u and v
    such that c and d are also adjacent.
    Uses bitmask neighbor sets for speed."""
    common = nbr_masks[u] & nbr_masks[v]
    # Check if any two vertices in common are adjacent
    temp = common
    while temp:
        c = (temp & -temp).bit_length() - 1
        # Check if c has any neighbor in common \ {c}
        if nbr_masks[c] & (common & ~(1 << c)):
            return True
        temp &= temp - 1
    return False


def compute_nbr_masks(adj):
    """Compute bitmask neighbor sets for each vertex. Returns Python int list."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        mask = 0
        for j in range(n):
            if adj[i, j]:
                mask |= 1 << j
        nbr[i] = mask
    return nbr


def compose_selective(blocks, strategy, d_cap, target_alpha=None, p=0.5, seed=42):
    """
    Compose multiple blocks with selective cross-edges.

    Args:
        blocks: list of numpy bool adjacency matrices (one per block)
        strategy: 'random', 'degree_balance', 'alpha_stop'
        d_cap: maximum degree cap
        target_alpha: for alpha_stop strategy
        p: edge probability for random strategy
        seed: random seed

    Returns:
        adj: composed graph adjacency matrix
        stats: dict with alpha, d_max, c, edges_added, etc.
    """
    rng = random.Random(seed)
    block_sizes = [b.shape[0] for b in blocks]
    n_total = sum(block_sizes)
    membership = get_block_membership(block_sizes)

    # Build disjoint union
    adj = build_disjoint_union(blocks)
    degrees = adj.sum(axis=1).astype(np.int32)
    nbr_masks = compute_nbr_masks(adj)

    # Enumerate all possible cross-edges
    cross_edges = []
    for i in range(n_total):
        for j in range(i + 1, n_total):
            if membership[i] != membership[j]:
                cross_edges.append((i, j))

    if strategy == "degree_balance":
        # Sort by sum of degrees ascending (prefer low-degree endpoints)
        # Recompute ordering iteratively: pick globally best edge each step
        edges_added = 0
        considered = set(range(len(cross_edges)))
        while considered:
            # Find best edge: lowest degree sum among uncapped, K4-safe
            best_idx = None
            best_score = float("inf")
            to_remove = []
            for idx in considered:
                i, j = cross_edges[idx]
                if degrees[i] >= d_cap or degrees[j] >= d_cap:
                    to_remove.append(idx)
                    continue
                score = degrees[i] + degrees[j]
                if score < best_score:
                    best_score = score
                    best_idx = idx
            for idx in to_remove:
                considered.discard(idx)
            if best_idx is None:
                break
            considered.discard(best_idx)
            i, j = cross_edges[best_idx]
            if degrees[i] >= d_cap or degrees[j] >= d_cap:
                continue
            if not would_create_k4(adj, nbr_masks, i, j):
                adj[i, j] = adj[j, i] = True
                degrees[i] += 1
                degrees[j] += 1
                nbr_masks[i] |= (1 << j)
                nbr_masks[j] |= (1 << i)
                edges_added += 1
    else:
        # random or alpha_stop: single pass over shuffled edges
        rng.shuffle(cross_edges)
        edges_added = 0
        alpha_check_interval = 5

        for i, j in cross_edges:
            if strategy == "random" and rng.random() > p:
                continue
            if degrees[i] >= d_cap or degrees[j] >= d_cap:
                continue
            if not would_create_k4(adj, nbr_masks, i, j):
                adj[i, j] = adj[j, i] = True
                degrees[i] += 1
                degrees[j] += 1
                nbr_masks[i] |= (1 << j)
                nbr_masks[j] |= (1 << i)
                edges_added += 1

                if strategy == "alpha_stop" and target_alpha is not None:
                    if edges_added % alpha_check_interval == 0:
                        if n_total <= 20:
                            a, _ = alpha_exact(adj)
                        else:
                            a, _, _ = alpha_sat(adj, timeout=10)
                        if a <= target_alpha:
                            break

    # Final scoring
    d_max = int(degrees.max())
    if n_total <= 20:
        alpha, _ = alpha_exact(adj)
    else:
        alpha, _, _ = alpha_sat(adj, timeout=30)

    c = compute_c_value(alpha, n_total, d_max)
    deg_seq = sorted(degrees.tolist(), reverse=True)

    return adj, {
        "alpha": int(alpha),
        "d_max": int(d_max),
        "c": round(c, 4) if c != float("inf") else None,
        "edges_added": edges_added,
        "total_edges": int(adj.sum()) // 2,
        "degree_sequence": deg_seq,
        "n": n_total,
        "block_sizes": block_sizes,
        "strategy": strategy,
        "d_cap": d_cap,
        "p": p if strategy == "random" else None,
        "target_alpha": target_alpha if strategy == "alpha_stop" else None,
        "seed": seed,
    }


# ============================================================================
# Degree-balance iterative variant (fast approximation)
# ============================================================================

def compose_degree_balance_fast(blocks, d_cap, seed=42):
    """Faster degree_balance: sort once, single pass with re-checks."""
    rng = random.Random(seed)
    block_sizes = [b.shape[0] for b in blocks]
    n_total = sum(block_sizes)
    membership = get_block_membership(block_sizes)

    adj = build_disjoint_union(blocks)
    degrees = adj.sum(axis=1).astype(np.int32)
    nbr_masks = compute_nbr_masks(adj)

    cross_edges = []
    for i in range(n_total):
        for j in range(i + 1, n_total):
            if membership[i] != membership[j]:
                cross_edges.append((i, j))

    # Sort by degree sum, break ties randomly
    rng.shuffle(cross_edges)
    cross_edges.sort(key=lambda e: degrees[e[0]] + degrees[e[1]])

    edges_added = 0
    for i, j in cross_edges:
        if degrees[i] >= d_cap or degrees[j] >= d_cap:
            continue
        if not would_create_k4(adj, nbr_masks, i, j):
            adj[i, j] = adj[j, i] = True
            degrees[i] += 1
            degrees[j] += 1
            nbr_masks[i] |= (1 << j)
            nbr_masks[j] |= (1 << i)
            edges_added += 1

    d_max = int(degrees.max())
    if n_total <= 20:
        alpha, _ = alpha_exact(adj)
    else:
        alpha, _, _ = alpha_sat(adj, timeout=30)

    c = compute_c_value(alpha, n_total, d_max)

    return adj, {
        "alpha": int(alpha),
        "d_max": int(d_max),
        "c": round(c, 4) if c != float("inf") else None,
        "edges_added": edges_added,
        "total_edges": int(adj.sum()) // 2,
        "degree_sequence": sorted(degrees.tolist(), reverse=True),
        "n": n_total,
        "block_sizes": block_sizes,
        "strategy": "degree_balance",
        "d_cap": d_cap,
        "seed": seed,
    }


# ============================================================================
# Configuration generation
# ============================================================================

def generate_configs(N):
    """Generate depth configurations for target graph size N."""
    configs = []

    if N == 16:
        configs = [
            # Depth 1 (2 blocks)
            {"name": "8+8", "sizes": [8, 8], "depth": 1},
            {"name": "7+9", "sizes": [7, 9], "depth": 1},
            {"name": "6+10", "sizes": [6, 10], "depth": 1},
            {"name": "5+11", "sizes": [5, 11], "depth": 1},
            # Depth 2 (3 blocks)
            {"name": "5+5+6", "sizes": [5, 5, 6], "depth": 2},
            {"name": "4+4+8", "sizes": [4, 4, 8], "depth": 2},
            {"name": "6+6+4", "sizes": [6, 6, 4], "depth": 2},
            # Depth 3 (4 blocks)
            {"name": "4+4+4+4", "sizes": [4, 4, 4, 4], "depth": 3},
            {"name": "3+5+4+4", "sizes": [3, 5, 4, 4], "depth": 3},
            # Depth 4 (5 blocks)
            {"name": "4+3+3+3+3", "sizes": [4, 3, 3, 3, 3], "depth": 4},
            {"name": "3+3+3+3+4", "sizes": [3, 3, 3, 3, 4], "depth": 4},
            # Depth 5 (6 blocks)
            {"name": "3+3+3+3+3+1", "sizes": [3, 3, 3, 3, 3, 1], "depth": 5},
            # Depth 15 (raw vertices)
            {"name": "raw_16x1", "sizes": [1] * 16, "depth": 15},
        ]
    elif N == 20:
        configs = [
            # Depth 1 (2 blocks) — only n<=8 blocks exist in library
            {"name": "8+8+4dummy", "sizes": [8, 8, 4], "depth": 2},
            # Depth 2 (3 blocks)
            {"name": "8+6+6", "sizes": [8, 6, 6], "depth": 2},
            {"name": "7+7+6", "sizes": [7, 7, 6], "depth": 2},
            # Depth 3 (4 blocks)
            {"name": "5+5+5+5", "sizes": [5, 5, 5, 5], "depth": 3},
            {"name": "6+6+4+4", "sizes": [6, 6, 4, 4], "depth": 3},
            # Depth 4 (5 blocks)
            {"name": "4+4+4+4+4", "sizes": [4, 4, 4, 4, 4], "depth": 4},
            {"name": "5+4+4+4+3", "sizes": [5, 4, 4, 4, 3], "depth": 4},
            # Depth 5 (6 blocks)
            {"name": "4+4+3+3+3+3", "sizes": [4, 4, 3, 3, 3, 3], "depth": 5},
            {"name": "4+3+3+3+3+4", "sizes": [4, 3, 3, 3, 3, 4], "depth": 5},
            # Depth 6 (7 blocks)
            {"name": "3+3+3+3+3+3+2", "sizes": [3, 3, 3, 3, 3, 3, 2], "depth": 6},
            # Raw
            {"name": "raw_20x1", "sizes": [1] * 20, "depth": 19},
        ]
    elif N == 24:
        configs = [
            # Depth 2 (3 blocks)
            {"name": "8+8+8", "sizes": [8, 8, 8], "depth": 2},
            # Depth 3 (4 blocks)
            {"name": "6+6+6+6", "sizes": [6, 6, 6, 6], "depth": 3},
            {"name": "8+8+4+4", "sizes": [8, 8, 4, 4], "depth": 3},
            # Depth 4 (5 blocks)
            {"name": "5+5+5+5+4", "sizes": [5, 5, 5, 5, 4], "depth": 4},
            # Depth 5 (6 blocks)
            {"name": "4+4+4+4+4+4", "sizes": [4, 4, 4, 4, 4, 4], "depth": 5},
            # Depth 6 (7 blocks)
            {"name": "4+4+4+3+3+3+3", "sizes": [4, 4, 4, 3, 3, 3, 3], "depth": 6},
            # Depth 7 (8 blocks)
            {"name": "3+3+3+3+3+3+3+3", "sizes": [3, 3, 3, 3, 3, 3, 3, 3], "depth": 7},
            # Raw
            {"name": "raw_24x1", "sizes": [1] * 24, "depth": 23},
        ]
    else:
        # Generic: equal-size blocks at various depths
        for num_blocks in [2, 3, 4, N]:
            base = N // num_blocks
            rem = N % num_blocks
            sizes = [base + 1] * rem + [base] * (num_blocks - rem)
            depth = num_blocks - 1
            name = "+".join(str(s) for s in sizes)
            configs.append({"name": name, "sizes": sizes, "depth": depth})

    return configs


# ============================================================================
# Run experiment
# ============================================================================

def run_single_trial(library, config, strategy, d_cap, p, target_alpha, seed):
    """Run a single trial: select blocks, compose, score."""
    rng = random.Random(seed)

    # Select blocks from library
    blocks = []
    for s in config["sizes"]:
        if s <= 8:
            blocks.append(select_block_from_library(library, s, rng))
        else:
            # For sizes > 8: use smaller blocks from library combined,
            # or just use empty graph (isolated vertices)
            # Since library only goes up to n=8, use empty graph for n>8
            blocks.append(np.zeros((s, s), dtype=np.bool_))

    if strategy == "degree_balance":
        _, stats = compose_degree_balance_fast(blocks, d_cap, seed=seed)
    else:
        _, stats = compose_selective(
            blocks, strategy, d_cap,
            target_alpha=target_alpha, p=p, seed=seed
        )

    stats["config_name"] = config["name"]
    stats["depth"] = config["depth"]
    return stats


def run_experiment_for_n(N, library, num_seeds=20, args=None):
    """Run full experiment for a given N."""
    print(f"\n{'='*60}")
    print(f"EXPERIMENT: N={N}")
    print(f"{'='*60}")

    configs = generate_configs(N)
    sat_opt = load_sat_optimal(N)

    if sat_opt:
        print(f"  SAT-optimal: c={sat_opt['c']:.4f}, α={sat_opt['alpha']}, d_max={sat_opt['d_max']}")
    else:
        print(f"  SAT-optimal: not available")

    d_caps = [4, 5, 6, 8]
    p_values = [0.3, 0.5, 0.7, 1.0]
    # For alpha_stop at N=16, target alpha = 4 (SAT-optimal)
    target_alphas = {16: 4, 20: 4, 24: 6}
    target_alpha = target_alphas.get(N, max(1, N // 4))

    all_results = []
    total_trials = 0

    for config in configs:
        print(f"\n  Config: {config['name']} (depth={config['depth']})")

        # Strategy 1: random
        for d_cap in d_caps:
            for p in p_values:
                for seed in range(num_seeds):
                    stats = run_single_trial(
                        library, config, "random", d_cap, p, None, seed
                    )
                    all_results.append(stats)
                    total_trials += 1

        # Strategy 2: degree_balance
        for d_cap in d_caps:
            for seed in range(num_seeds):
                stats = run_single_trial(
                    library, config, "degree_balance", d_cap, 1.0, None, seed
                )
                all_results.append(stats)
                total_trials += 1

        # Strategy 3: alpha_stop
        for d_cap in d_caps:
            for seed in range(num_seeds):
                stats = run_single_trial(
                    library, config, "alpha_stop", d_cap, 1.0, target_alpha, seed
                )
                all_results.append(stats)
                total_trials += 1

        # Progress
        valid = [r for r in all_results if r["c"] is not None]
        if valid:
            best = min(valid, key=lambda r: r["c"])
            print(f"    Trials so far: {total_trials}, best c={best['c']:.4f} "
                  f"(α={best['alpha']}, d={best['d_max']}, {best['strategy']}, "
                  f"config={best['config_name']})")

    print(f"\n  Total trials: {total_trials}")
    return all_results, sat_opt


# ============================================================================
# Analysis
# ============================================================================

def analyze_results(all_results, N, sat_opt):
    """Analyze and summarize results."""
    print(f"\n{'='*60}")
    print(f"ANALYSIS: N={N}")
    print(f"{'='*60}")

    valid = [r for r in all_results if r["c"] is not None]
    if not valid:
        print("  No valid results!")
        return {}, {}, []

    # === Best c by depth ===
    depth_best = {}
    for r in valid:
        d = r["depth"]
        if d not in depth_best or r["c"] < depth_best[d]["c"]:
            depth_best[d] = r

    print(f"\n  Best c by depth:")
    print(f"  {'Depth':<6} {'Config':<15} {'Strategy':<16} {'c':<8} {'α':<4} {'d_max':<6} {'Gap to SAT'}")
    print(f"  {'-'*70}")
    for d in sorted(depth_best.keys()):
        r = depth_best[d]
        gap = f"{r['c'] - sat_opt['c']:.4f}" if sat_opt else "N/A"
        strat_info = r["strategy"]
        if r["strategy"] == "random":
            strat_info += f" p={r.get('p', '?')}"
        print(f"  {d:<6} {r['config_name']:<15} {strat_info:<16} {r['c']:<8.4f} "
              f"{r['alpha']:<4} {r['d_max']:<6} {gap}")

    # === Best c by strategy ===
    strat_best = {}
    for r in valid:
        s = r["strategy"]
        if s not in strat_best or r["c"] < strat_best[s]["c"]:
            strat_best[s] = r

    print(f"\n  Best c by strategy:")
    for s in ["random", "degree_balance", "alpha_stop"]:
        if s in strat_best:
            r = strat_best[s]
            print(f"    {s:<16}: c={r['c']:.4f}, α={r['alpha']}, d_max={r['d_max']}, "
                  f"config={r['config_name']}, d_cap={r['d_cap']}")

    # === Best c by d_cap ===
    dcap_best = {}
    for r in valid:
        dc = r["d_cap"]
        if dc not in dcap_best or r["c"] < dcap_best[dc]["c"]:
            dcap_best[dc] = r

    print(f"\n  Best c by d_cap:")
    for dc in sorted(dcap_best.keys()):
        r = dcap_best[dc]
        print(f"    d_cap={dc}: c={r['c']:.4f}, α={r['alpha']}, d_max={r['d_max']}, "
              f"config={r['config_name']}, strategy={r['strategy']}")

    # === Degree sequence of top 5 ===
    top5 = sorted(valid, key=lambda r: r["c"])[:5]
    print(f"\n  Top 5 graphs:")
    for i, r in enumerate(top5):
        ds = r["degree_sequence"]
        ds_str = str(ds[:16]) + ("..." if len(ds) > 16 else "")
        print(f"    #{i+1}: c={r['c']:.4f}, α={r['alpha']}, d_max={r['d_max']}, "
              f"config={r['config_name']}, strategy={r['strategy']}")
        print(f"          deg_seq={ds_str}")

    if sat_opt:
        print(f"\n    SAT-optimal: c={sat_opt['c']:.4f}, α={sat_opt['alpha']}, "
              f"d_max={sat_opt['d_max']}, deg=[{sat_opt['d_max']}]*{N}")

    # === Depth ablation table ===
    depth_ablation = []
    for d in sorted(depth_best.keys()):
        r = depth_best[d]
        entry = {
            "depth": d,
            "config": r["config_name"],
            "best_strategy": r["strategy"],
            "best_c": r["c"],
            "alpha": r["alpha"],
            "d_max": r["d_max"],
            "d_cap": r["d_cap"],
            "gap_to_sat": round(r["c"] - sat_opt["c"], 4) if sat_opt else None,
        }
        if r["strategy"] == "random":
            entry["p"] = r.get("p")
        depth_ablation.append(entry)

    # === Strategy comparison ===
    strategy_comparison = {}
    for s in ["random", "degree_balance", "alpha_stop"]:
        s_results = [r for r in valid if r["strategy"] == s]
        if not s_results:
            continue
        best = min(s_results, key=lambda r: r["c"])
        cs = [r["c"] for r in s_results]
        strategy_comparison[s] = {
            "best_c": best["c"],
            "mean_c": round(np.mean(cs), 4),
            "median_c": round(np.median(cs), 4),
            "best_config": best["config_name"],
            "best_d_cap": best["d_cap"],
            "best_alpha": best["alpha"],
            "best_d_max": best["d_max"],
            "num_trials": len(s_results),
        }

    return depth_ablation, strategy_comparison, top5


# ============================================================================
# Plotting
# ============================================================================

def make_plots(all_results, N, sat_opt, depth_ablation):
    """Generate analysis plots."""
    valid = [r for r in all_results if r["c"] is not None]
    if not valid:
        return

    # --- Plot 1: c vs depth ---
    fig, ax = plt.subplots(figsize=(10, 6))

    # Scatter all results by depth
    depths = [r["depth"] for r in valid]
    cs = [r["c"] for r in valid]
    strategies = [r["strategy"] for r in valid]

    colors = {"random": "blue", "degree_balance": "green", "alpha_stop": "red"}
    for s in ["random", "degree_balance", "alpha_stop"]:
        mask = [strategies[i] == s for i in range(len(strategies))]
        d_s = [depths[i] for i in range(len(depths)) if mask[i]]
        c_s = [cs[i] for i in range(len(cs)) if mask[i]]
        ax.scatter(d_s, c_s, c=colors[s], alpha=0.15, s=10, label=f"{s} (all)")

    # Best per depth
    if depth_ablation:
        da_depths = [e["depth"] for e in depth_ablation]
        da_cs = [e["best_c"] for e in depth_ablation]
        ax.plot(da_depths, da_cs, "k-o", linewidth=2, markersize=8, label="Best per depth", zorder=5)

    # Reference lines
    if sat_opt:
        ax.axhline(y=sat_opt["c"], color="gold", linestyle="--", linewidth=2, label=f"SAT-optimal ({sat_opt['c']:.4f})")
    ax.axhline(y=0.90, color="purple", linestyle=":", linewidth=1.5, label="IS-join baseline (~0.90)")

    ax.set_xlabel("Depth (number of blocks - 1)", fontsize=12)
    ax.set_ylabel("c = α·d_max / (N·ln d_max)", fontsize=12)
    ax.set_title(f"Selective Cross-Edge: c vs Depth (N={N})", fontsize=14)
    ax.legend(fontsize=9, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, f"c_vs_depth_n{N}.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved c_vs_depth_n{N}.png")

    # --- Plot 2: c by strategy (box plots) ---
    fig, ax = plt.subplots(figsize=(10, 6))
    strat_data = defaultdict(list)
    for r in valid:
        strat_data[r["strategy"]].append(r["c"])

    labels = []
    data = []
    for s in ["random", "degree_balance", "alpha_stop"]:
        if s in strat_data:
            labels.append(s)
            data.append(strat_data[s])

    bp = ax.boxplot(data, labels=labels, patch_artist=True)
    box_colors = ["#4488cc", "#44cc88", "#cc4444"]
    for patch, color in zip(bp["boxes"], box_colors[:len(data)]):
        patch.set_facecolor(color)
        patch.set_alpha(0.5)

    if sat_opt:
        ax.axhline(y=sat_opt["c"], color="gold", linestyle="--", linewidth=2, label=f"SAT-optimal ({sat_opt['c']:.4f})")
    ax.axhline(y=0.90, color="purple", linestyle=":", linewidth=1.5, label="IS-join baseline (~0.90)")

    ax.set_ylabel("c = α·d_max / (N·ln d_max)", fontsize=12)
    ax.set_title(f"Strategy Comparison (N={N})", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, f"c_by_strategy_n{N}.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved c_by_strategy_n{N}.png")

    # --- Plot 3: degree sequences of best graphs ---
    top5 = sorted(valid, key=lambda r: r["c"])[:5]
    fig, ax = plt.subplots(figsize=(10, 6))
    for i, r in enumerate(top5):
        ds = sorted(r["degree_sequence"], reverse=True)
        ax.plot(range(len(ds)), ds, "o-", markersize=4,
                label=f"#{i+1}: c={r['c']:.4f} ({r['strategy']}, {r['config_name']})")

    if sat_opt:
        ax.plot(range(N), [sat_opt["d_max"]] * N, "k--", linewidth=2,
                label=f"SAT-optimal ({sat_opt['d_max']}-regular)")

    ax.set_xlabel("Vertex (sorted by degree)", fontsize=12)
    ax.set_ylabel("Degree", fontsize=12)
    ax.set_title(f"Degree Sequences of Best Graphs (N={N})", fontsize=14)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOT_DIR, f"degree_sequences_n{N}.png"), dpi=150)
    plt.close(fig)
    print(f"  Saved degree_sequences_n{N}.png")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Selective cross-edge experiment")
    parser.add_argument("--seeds", type=int, default=20, help="Seeds per config")
    parser.add_argument("--n-values", type=int, nargs="+", default=[16, 20, 24],
                        help="Target N values")
    args = parser.parse_args()

    os.makedirs(PLOT_DIR, exist_ok=True)

    print("Loading block library...")
    library = load_library()

    # Check available block sizes
    lib_sizes = defaultdict(int)
    for b in library:
        lib_sizes[b["n"]] += 1
    print(f"  Block sizes: {dict(sorted(lib_sizes.items()))}")

    all_summaries = {}

    for N in args.n_values:
        t0 = time.time()
        results, sat_opt = run_experiment_for_n(N, library, num_seeds=args.seeds, args=args)
        elapsed = time.time() - t0
        print(f"\n  N={N}: {len(results)} trials in {elapsed:.1f}s")

        # Save raw results
        results_path = os.path.join(OUTDIR, f"results_n{N}.json")
        with open(results_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"  Saved {results_path}")

        # Analyze
        depth_ablation, strategy_comparison, top5 = analyze_results(results, N, sat_opt)

        # Save analysis
        depth_path = os.path.join(OUTDIR, f"depth_ablation_n{N}.json")
        with open(depth_path, "w") as f:
            json.dump(depth_ablation, f, indent=2)

        strat_path = os.path.join(OUTDIR, f"strategy_comparison_n{N}.json")
        with open(strat_path, "w") as f:
            json.dump(strategy_comparison, f, indent=2)

        # Plots
        make_plots(results, N, sat_opt, depth_ablation)

        all_summaries[N] = {
            "depth_ablation": depth_ablation,
            "strategy_comparison": strategy_comparison,
            "sat_optimal": sat_opt,
            "num_trials": len(results),
            "elapsed_s": round(elapsed, 1),
        }

    # Save combined summary
    summary_path = os.path.join(OUTDIR, "experiment_summary.json")
    # Convert keys to strings for JSON
    json_summaries = {str(k): v for k, v in all_summaries.items()}
    with open(summary_path, "w") as f:
        json.dump(json_summaries, f, indent=2)
    print(f"\nSaved {summary_path}")

    # === Final summary ===
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    for N in args.n_values:
        if N not in all_summaries:
            continue
        s = all_summaries[N]
        da = s["depth_ablation"]
        if da:
            best = min(da, key=lambda e: e["best_c"])
            sat_c = s["sat_optimal"]["c"] if s["sat_optimal"] else None
            print(f"\n  N={N}: best c={best['best_c']:.4f} at depth={best['depth']} "
                  f"({best['config']}, {best['best_strategy']})")
            if sat_c:
                print(f"    SAT-optimal: c={sat_c:.4f}, gap={best['best_c'] - sat_c:.4f}")
            print(f"    IS-join baseline: ~0.90, improvement={0.90 - best['best_c']:.4f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
