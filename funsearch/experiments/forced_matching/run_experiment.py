#!/usr/bin/env python3
"""
Forced-Matching Construction
=============================
Tests whether α-forced connector matchings produce competitive K₄-free graphs.

A vertex v in block B is α-forced iff α(B - v) = α(B) - 1 (v in every max IS).
Joining blocks via a matching on α-forced vertices is predicted to drop α by
exactly |M| while increasing d_max by at most 1.

Pipeline:
    1. Scan library for α-forced vertices per block.
    2. Build k-copy single-type constructions with maximum forced matchings.
    3. Greedy mixed constructions at target N.
    4. Verify predicted α vs actual α (SAT / bitmask B&B) on every graph.
    5. Plot tradeoffs and compare to SAT-optimal / random baselines.

Usage:
    micromamba run -n funsearch python experiments/forced_matching/run_experiment.py
"""

import argparse
import csv
import importlib.util
import itertools
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
import networkx as nx

sys.stdout.reconfigure(line_buffering=True)

_HERE = os.path.dirname(os.path.abspath(__file__))

# --- import shared utilities from block_decomposition via importlib ---

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_bd = _load_module(
    "block_decomp",
    os.path.join(_HERE, "..", "block_decomposition", "run_experiment.py"),
)

alpha_exact = _bd.alpha_exact
alpha_sat = _bd.alpha_sat
alpha_of_subset = _bd.alpha_of_subset
is_k4_free = _bd.is_k4_free
compute_c_value = _bd.compute_c_value
adj_to_graph6 = _bd.adj_to_graph6

LIBRARY_PATH = os.path.join(_HERE, "..", "block_decomposition", "library.json")
PARETO_DIR = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "reference", "pareto")
)
OUTDIR = _HERE


# ============================================================================
# Data loading
# ============================================================================

def load_library():
    with open(LIBRARY_PATH) as f:
        lib = json.load(f)
    return lib


def load_sat_optimal_map(max_n=35):
    """Return {N: c_min} over SAT pareto frontier."""
    out = {}
    for N in range(2, max_n + 1):
        path = os.path.join(PARETO_DIR, f"pareto_n{N}.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            data = json.load(f)
        frontier = [
            e for e in data.get("pareto_frontier", [])
            if e.get("c_log") is not None
        ]
        if frontier:
            best = min(frontier, key=lambda e: e["c_log"])
            out[N] = {
                "c": best["c_log"],
                "alpha": best["alpha"],
                "d_max": best["d_max"],
            }
    return out


# ============================================================================
# Block analysis
# ============================================================================

def block_to_adj(block):
    n = block["n"]
    adj = np.zeros((n, n), dtype=np.bool_)
    for u, v in block["edges"]:
        adj[u, v] = adj[v, u] = True
    return adj


def block_has_triangle(adj):
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j] and (nbr[i] & nbr[j]):
                return True
    return False


def extract_forced_vertices(block):
    """Return sorted list of α-forced vertex indices from library data.
    v is α-forced iff {v} appears as a size-1 alpha_dropping_set."""
    forced = set()
    for d in block.get("alpha_dropping_sets", []):
        if d["size"] == 1:
            forced.add(d["vertices"][0])
    return sorted(forced)


def linear_drop_capacity(adj, forced, alpha, max_check=4):
    """Find max k such that for ALL k-subsets T of forced,
    α(B - T) = α - k. This is the max number of forced vertices that
    can be simultaneously 'consumed' with linear α accounting.

    Also returns the largest SINGLE subset T* (cardinality) that achieves
    α(B - T*) = α - |T*|, i.e., the largest linear-drop witness subset.
    """
    n = adj.shape[0]
    if not forced:
        return 0, 0, frozenset()
    all_verts_mask = (1 << n) - 1

    # Worst-case k: largest k with EVERY k-subset satisfying α = α-k
    worst_k = 0
    for k in range(1, min(len(forced), max_check) + 1):
        ok = True
        for T in itertools.combinations(forced, k):
            mask = all_verts_mask
            for v in T:
                mask &= ~(1 << v)
            if alpha_of_subset(adj, mask) != alpha - k:
                ok = False
                break
        if ok:
            worst_k = k
        else:
            break

    # Best-case: largest single subset witnessing linear drop
    best_k = worst_k
    best_T = frozenset()
    if worst_k > 0:
        best_T = frozenset(forced[:worst_k])
    for k in range(worst_k + 1, min(len(forced), max_check) + 1):
        for T in itertools.combinations(forced, k):
            mask = all_verts_mask
            for v in T:
                mask &= ~(1 << v)
            if alpha_of_subset(adj, mask) == alpha - k:
                best_k = k
                best_T = frozenset(T)
                break
    return worst_k, best_k, best_T


def degree_of(adj, v):
    return int(adj[v].sum())


def scan_blocks(library, compute_linearity=True, max_check=6):
    """Produce per-block records including forced-vertex stats.

    If compute_linearity: also compute worst-case and best-case linear drop
    capacity k* (max # of forced vertices removable with exact α = α-k drop).
    """
    records = []
    for b in library:
        adj = block_to_adj(b)
        forced = extract_forced_vertices(b)
        tri = block_has_triangle(adj)
        n = b["n"]
        alpha = b["alpha"]
        d_max = b["d_max"]
        forced_degs = [degree_of(adj, v) for v in forced]
        min_forced_deg = min(forced_degs) if forced_degs else None

        worst_k = best_k = 0
        best_T = frozenset()
        if compute_linearity and forced:
            worst_k, best_k, best_T = linear_drop_capacity(
                adj, forced, alpha, max_check=min(max_check, len(forced))
            )

        records.append({
            "block_id": b["block_id"],
            "n": n,
            "alpha": alpha,
            "d_max": d_max,
            "num_forced": len(forced),
            "forced": forced,
            "forced_degrees": forced_degs,
            "min_forced_deg": min_forced_deg,
            "alpha_ratio": alpha / n,
            "forced_ratio": len(forced) / n,
            "worst_linear_k": worst_k,
            "best_linear_k": best_k,
            "linear_witness": sorted(best_T),
            "is_triangle_free": not tri,
            "g6": b["g6"],
            "edges": b["edges"],
        })
    return records


# ============================================================================
# Graph construction via forced matching
# ============================================================================

def build_matched_graph(blocks, matching):
    """
    blocks: list of block records (dicts with 'n' and 'edges' in block-local indices)
    matching: list of (block_i, vertex_u, block_j, vertex_v) — LOCAL vertex indices

    Returns (adj, offsets, predicted_alpha, matched_vertices_per_block).
    """
    sizes = [b["n"] for b in blocks]
    offsets = [0]
    for s in sizes:
        offsets.append(offsets[-1] + s)
    N = offsets[-1]

    adj = np.zeros((N, N), dtype=np.bool_)
    for bi, block in enumerate(blocks):
        o = offsets[bi]
        for u, v in block["edges"]:
            adj[o + u, o + v] = True
            adj[o + v, o + u] = True

    used = [[] for _ in blocks]
    for (bi, u, bj, v) in matching:
        gu = offsets[bi] + u
        gv = offsets[bj] + v
        adj[gu, gv] = True
        adj[gv, gu] = True
        used[bi].append(u)
        used[bj].append(v)

    predicted_alpha = sum(b["alpha"] for b in blocks) - len(matching)
    return adj, offsets, predicted_alpha, used


# ============================================================================
# Max matching on the cross-block forced graph
# ============================================================================

def max_forced_matching(blocks, use_linear_witness=True, prefer_low_degree=True):
    """
    Find a max matching over cross-block edges between forced vertices.

    If use_linear_witness: per block, only use forced vertices in its
    'linear_witness' subset (a set verified to drop α linearly). This keeps
    the predicted α = Σα_i - |M| accounting sound.
    """
    G = nx.Graph()
    available = {}  # (block_idx, local_vertex) -> (du)
    for bi, block in enumerate(blocks):
        if use_linear_witness and "linear_witness" in block and block.get("best_linear_k", 0) > 0:
            candidates = list(block["linear_witness"])
        else:
            candidates = list(block["forced"])
        for v in candidates:
            # internal degree of v
            du = dict(zip(block["forced"], block["forced_degrees"])).get(
                v, degree_of(block_to_adj(block), v)
            )
            available[(bi, v)] = du
            G.add_node((bi, v))

    for (bi, u), (bj, v) in itertools.combinations(available.keys(), 2):
        if bi == bj:
            continue
        w = 1.0
        if prefer_low_degree:
            w = 2.0 - (available[(bi, u)] + available[(bj, v)]) / (
                2 * max(1, max(blocks[bi]["d_max"], blocks[bj]["d_max"]))
            )
        G.add_edge((bi, u), (bj, v), weight=w)

    if G.number_of_edges() == 0:
        return []

    matching = nx.max_weight_matching(G, maxcardinality=True)

    result = []
    for (bi, u), (bj, v) in matching:
        result.append((bi, u, bj, v))
    return result


# ============================================================================
# Actual α computation (switches between exact and SAT by size)
# ============================================================================

def compute_alpha(adj, timeout=60):
    n = adj.shape[0]
    # alpha_exact (bitmask B&B) is fast only for small or dense graphs.
    # For sparse matching-style graphs at n > ~20 it blows up, so prefer
    # alpha_sat (SAT binary search with CardEnc) for anything larger.
    if n <= 16:
        a, _ = alpha_exact(adj)
        return int(a), False
    a, _, timed_out = alpha_sat(adj, timeout=timeout)
    return int(a), bool(timed_out)


# ============================================================================
# Sweep: single-type construction
# ============================================================================

def evaluate_single_type_sweep(block, k_max, timeout=60, verify_alpha=True,
                               use_linear_witness=True):
    """For block B, build disjoint union of k copies with max forced matching.
    Returns list of result dicts across k = 2 .. k_max.

    Uses linear_witness per copy so the predicted α = Σα - |M| is correct.
    """
    results = []
    if not block["forced"]:
        return results

    for k in range(2, k_max + 1):
        blocks = [block] * k
        matching = max_forced_matching(blocks,
                                       use_linear_witness=use_linear_witness,
                                       prefer_low_degree=True)
        if not matching:
            continue

        adj, offsets, predicted_alpha, used = build_matched_graph(blocks, matching)
        N = adj.shape[0]

        # K4-freeness + actual α
        k4_ok = is_k4_free(adj)
        d_max_actual = int(adj.sum(axis=1).max())

        if verify_alpha:
            actual_alpha, timed_out = compute_alpha(adj, timeout=timeout)
        else:
            actual_alpha = predicted_alpha
            timed_out = False

        c = compute_c_value(actual_alpha, N, d_max_actual)
        c_predicted = compute_c_value(predicted_alpha, N, d_max_actual)

        results.append({
            "construction": "single",
            "block_id": block["block_id"],
            "block_n": block["n"],
            "block_alpha": block["alpha"],
            "block_forced": len(block["forced"]),
            "k_copies": k,
            "N": N,
            "num_matching": len(matching),
            "predicted_alpha": int(predicted_alpha),
            "actual_alpha": int(actual_alpha),
            "alpha_gap": int(actual_alpha - predicted_alpha),
            "d_max": d_max_actual,
            "k4_free": bool(k4_ok),
            "c": round(float(c), 4) if math.isfinite(c) else None,
            "c_predicted": round(float(c_predicted), 4) if math.isfinite(c_predicted) else None,
            "alpha_timed_out": timed_out,
            "g6": adj_to_graph6(adj),
        })
    return results


# ============================================================================
# Mixed-type greedy sweep
# ============================================================================

def greedy_mixed_sweep(block_pool, N_targets, beam_size=5, verify_alpha=True, timeout=60):
    """
    For each target N, greedily select a multiset of blocks (from block_pool)
    and construct forced matching. Picks blocks that minimize c at each step.
    """
    results = []
    for N in N_targets:
        # Try small combinations: 2-3 different block types, with replication.
        # Beam search across sequences of blocks; at each step, add a block that
        # improves (or maintains) projected c, subject to sum(n_i) ≤ N.
        best = None
        candidates = []

        # Seed with each block as starter
        for b in block_pool:
            if b["n"] > N:
                continue
            if not b["forced"]:
                continue
            candidates.append(([b], b["n"]))

        for step in range(10):  # cap depth
            new_candidates = []
            for seq, cur_N in candidates:
                if cur_N == N:
                    new_candidates.append((seq, cur_N))
                    continue
                for b in block_pool:
                    if cur_N + b["n"] > N:
                        continue
                    if not b["forced"]:
                        continue
                    new_candidates.append((seq + [b], cur_N + b["n"]))
            # Prune: deduplicate by block_id multiset, keep those with sum
            seen = set()
            uniq = []
            for seq, cn in new_candidates:
                key = (cn, tuple(sorted(b["block_id"] for b in seq)))
                if key in seen:
                    continue
                seen.add(key)
                uniq.append((seq, cn))
            # Rank by predicted c (rough: sum α_i - floor(total_forced/2)) / (sum n_i log(d_max+1))
            def score(seq_cn):
                seq, cn = seq_cn
                sum_alpha = sum(b["alpha"] for b in seq)
                # Per-block usable forced endpoints (linear witness).
                total_usable = sum(b.get("best_linear_k", 0) for b in seq)
                m_est = total_usable // 2  # matching edges
                d_est = max(b["d_max"] for b in seq) + 1
                pred_alpha = sum_alpha - m_est
                if cn == 0 or d_est <= 1:
                    return float("inf")
                return pred_alpha * d_est / (cn * math.log(d_est))
            uniq.sort(key=score)
            candidates = uniq[:beam_size * 4]
            # If any reached N, narrow candidates
            done = [c for c in candidates if c[1] == N]
            if done:
                candidates = done[:beam_size]
                break

        # Filter to exactly N and evaluate
        for seq, cn in candidates:
            if cn != N:
                continue
            matching = max_forced_matching(seq, prefer_low_degree=True)
            if not matching:
                continue
            adj, offsets, predicted_alpha, used = build_matched_graph(seq, matching)

            k4_ok = is_k4_free(adj)
            d_max_actual = int(adj.sum(axis=1).max())
            if verify_alpha:
                actual_alpha, timed_out = compute_alpha(adj, timeout=timeout)
            else:
                actual_alpha = predicted_alpha
                timed_out = False
            c = compute_c_value(actual_alpha, N, d_max_actual)

            result = {
                "construction": "mixed",
                "N": N,
                "block_ids": [b["block_id"] for b in seq],
                "block_sizes": [b["n"] for b in seq],
                "block_alphas": [b["alpha"] for b in seq],
                "num_blocks": len(seq),
                "num_matching": len(matching),
                "predicted_alpha": int(predicted_alpha),
                "actual_alpha": int(actual_alpha),
                "alpha_gap": int(actual_alpha - predicted_alpha),
                "d_max": d_max_actual,
                "k4_free": bool(k4_ok),
                "c": round(float(c), 4) if math.isfinite(c) else None,
                "alpha_timed_out": timed_out,
                "g6": adj_to_graph6(adj),
            }
            if best is None or (result["c"] is not None and (best.get("c") is None or result["c"] < best["c"])):
                best = result

        if best is not None:
            results.append(best)
            print(f"    mixed N={N}: c={best['c']}, α={best['actual_alpha']} "
                  f"(pred {best['predicted_alpha']}), d={best['d_max']}, "
                  f"{best['num_blocks']} blocks, gap={best['alpha_gap']}")
    return results


# ============================================================================
# Stress tests: reuse & non-forced endpoints
# ============================================================================

def stress_reuse_forced(block):
    """Test reusing the same forced vertex for 2 cross-edges.
    Build 3 copies of block, match (0_B1 - 0_B2) and (0_B1 - 0_B3) sharing vertex 0 of B1.
    Compare predicted (α - 2) vs actual.
    """
    if not block["forced"]:
        return None
    v = block["forced"][0]
    # Pick a second forced vertex on B2 and B3 (or the same v)
    v2 = block["forced"][0]
    v3 = block["forced"][0]
    blocks = [block, block, block]
    # Non-matching: vertex v of block 0 used twice. Not a legal matching but
    # we want to measure the α drop.
    matching = [(0, v, 1, v2), (0, v, 2, v3)]
    adj, offsets, predicted_alpha, _ = build_matched_graph(blocks, matching)
    actual, _ = compute_alpha(adj)
    return {
        "test": "reuse_forced_vertex_twice",
        "block_id": block["block_id"],
        "predicted_alpha_if_counted_once": sum(b["alpha"] for b in blocks) - 1,
        "predicted_alpha_naive_sum": sum(b["alpha"] for b in blocks) - 2,
        "actual_alpha": int(actual),
        "N": adj.shape[0],
        "d_max": int(adj.sum(axis=1).max()),
        "k4_free": bool(is_k4_free(adj)),
    }


def stress_nonforced_endpoints(block):
    """Test matching a NON-forced vertex to a forced vertex.
    Predicted drop is unclear; this measures it."""
    if not block["forced"]:
        return None
    n = block["n"]
    non_forced = [v for v in range(n) if v not in block["forced"]]
    if not non_forced:
        return None
    blocks = [block, block]
    # Edge from non-forced 'nu' in block 0 to forced 'fv' in block 1
    nu = non_forced[0]
    fv = block["forced"][0]
    matching = [(0, nu, 1, fv)]
    adj, _, predicted_alpha, _ = build_matched_graph(blocks, matching)
    actual, _ = compute_alpha(adj)
    # For comparison: both-forced
    matching_ff = [(0, fv, 1, fv)]
    adj_ff, _, pred_ff, _ = build_matched_graph([block, block], matching_ff)
    actual_ff, _ = compute_alpha(adj_ff)
    return {
        "test": "nonforced_endpoint",
        "block_id": block["block_id"],
        "predicted_alpha_both_forced": int(pred_ff),
        "actual_alpha_both_forced": int(actual_ff),
        "predicted_alpha_mixed": int(predicted_alpha),
        "actual_alpha_mixed": int(actual),
        "alpha_drop_mixed": int(block["alpha"] * 2 - actual),
    }


# ============================================================================
# Plots
# ============================================================================

def plot_tradeoff(scan_records, block_best_c, out_path):
    """Scatter: x = α(B)/|V|, y = |S|/|V|, color = best c achievable using that block."""
    fig, ax = plt.subplots(figsize=(9, 6))
    xs, ys, cs, sizes = [], [], [], []
    for rec in scan_records:
        if rec["num_forced"] == 0:
            continue
        bid = rec["block_id"]
        bc = block_best_c.get(bid)
        if bc is None:
            continue
        xs.append(rec["alpha_ratio"])
        ys.append(rec["forced_ratio"])
        cs.append(bc)
        sizes.append(10 + 5 * rec["n"])
    if not xs:
        print("  (no tradeoff points)")
        return
    sc = ax.scatter(xs, ys, c=cs, s=sizes, cmap="viridis_r", alpha=0.7, edgecolors="k", linewidths=0.3)
    cb = plt.colorbar(sc, ax=ax)
    cb.set_label("best c achieved (lower is better)")
    ax.set_xlabel(r"$\alpha(B)/|V(B)|$ (base independence ratio)")
    ax.set_ylabel(r"$|S|/|V(B)|$ (forced-vertex density)")
    ax.set_title("Block tradeoff: forced density vs α-ratio\n(size = |V(B)|)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_c_vs_n(single_results, mixed_results, sat_opt, out_path, random_baseline=None):
    """c vs N for top blocks + mixed, overlaid with SAT-optimal and random baseline."""
    fig, ax = plt.subplots(figsize=(10, 6))

    # Group single-type by block_id, pick top 5 by min c
    by_block = defaultdict(list)
    for r in single_results:
        by_block[r["block_id"]].append(r)
    best_per_block = {bid: min(rs, key=lambda r: r["c"] if r["c"] is not None else float("inf"))
                      for bid, rs in by_block.items()}
    top5 = sorted(best_per_block.items(),
                  key=lambda kv: kv[1]["c"] if kv[1]["c"] is not None else float("inf"))[:5]

    cmap = plt.cm.tab10
    for i, (bid, _) in enumerate(top5):
        series = sorted(by_block[bid], key=lambda r: r["N"])
        xs = [r["N"] for r in series if r["c"] is not None]
        ys = [r["c"] for r in series if r["c"] is not None]
        if xs:
            label = f"block#{bid} (n={series[0]['block_n']}, α={series[0]['block_alpha']}, |S|={series[0]['block_forced']})"
            ax.plot(xs, ys, "-o", color=cmap(i), label=label, markersize=4)

    # Mixed
    if mixed_results:
        xs = [r["N"] for r in mixed_results if r["c"] is not None]
        ys = [r["c"] for r in mixed_results if r["c"] is not None]
        if xs:
            ax.plot(xs, ys, "-s", color="black", label="mixed (greedy)", markersize=5, linewidth=2)

    # SAT-optimal
    if sat_opt:
        xs = sorted(sat_opt.keys())
        ys = [sat_opt[n]["c"] for n in xs]
        ax.plot(xs, ys, "--", color="red", label="SAT-optimal (c_log)", linewidth=2)

    # Random baseline line
    if random_baseline is not None:
        ax.axhline(random_baseline, linestyle=":", color="gray",
                   label=f"random edge baseline ~{random_baseline:.2f}")

    ax.set_xlabel("N")
    ax.set_ylabel(r"$c = \alpha \cdot d_{\max} / (N \log d_{\max})$")
    ax.set_title("c vs N: forced-matching vs SAT-optimal")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--k-max", type=int, default=20,
                        help="Max copies for single-type sweep")
    parser.add_argument("--top-blocks", type=int, default=60,
                        help="Number of blocks to include in single-type sweep (ranked by α-ratio asc)")
    parser.add_argument("--mixed-N", type=int, nargs="+",
                        default=[12, 14, 16, 18, 20, 22, 24, 26, 28, 30],
                        help="N values for mixed-construction sweep")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--pool-size", type=int, default=20,
                        help="Number of blocks available to mixed constructor (per size)")
    args = parser.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)

    t0 = time.time()
    print("Loading library...")
    library = load_library()
    print(f"  {len(library)} blocks loaded")

    print("Scanning blocks for α-forced vertices...")
    scan = scan_blocks(library)
    scan_with_forced = [r for r in scan if r["num_forced"] > 0]
    scan_with_forced.sort(key=lambda r: (r["alpha_ratio"], -r["forced_ratio"]))
    print(f"  {len(scan_with_forced)} blocks have ≥1 forced vertex")

    # --- Save block_scan.csv ---
    scan_csv = os.path.join(OUTDIR, "block_scan.csv")
    with open(scan_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "block_id", "n", "alpha", "d_max", "num_forced",
            "alpha_ratio", "forced_ratio",
            "worst_linear_k", "best_linear_k", "linear_witness",
            "is_triangle_free", "min_forced_deg", "forced", "g6",
        ])
        for rec in sorted(scan, key=lambda r: (r["alpha_ratio"], -r["num_forced"])):
            w.writerow([
                rec["block_id"], rec["n"], rec["alpha"], rec["d_max"],
                rec["num_forced"],
                f"{rec['alpha_ratio']:.4f}", f"{rec['forced_ratio']:.4f}",
                rec.get("worst_linear_k", 0), rec.get("best_linear_k", 0),
                "|".join(str(v) for v in rec.get("linear_witness", [])),
                int(rec["is_triangle_free"]),
                rec["min_forced_deg"] if rec["min_forced_deg"] is not None else "",
                "|".join(str(v) for v in rec["forced"]),
                rec["g6"],
            ])
    print(f"  Wrote {scan_csv}")

    # --- Rank blocks by asymptotic predicted c USING linear witness ---
    # Per copy, we can safely consume up to k* = best_linear_k forced vertices
    # with exact α-drop = k*. Max matching across k copies uses (k * k*) / 2
    # matching edges (each edge consumes 1 endpoint from each of 2 copies).
    # Predicted α = k·α - k·k* (per-copy loss = k*), total used forced endpoints
    # across matching = k·k*, matching edges = k·k*/2.
    # Asymptotic c ≈ (α - k*) · (d+1) / (n · log(d+1)).
    def predicted_c_asymptotic(r):
        n = r["n"]
        a = r["alpha"]
        k_star = r.get("best_linear_k", 0)
        d = r["d_max"] + (1 if k_star > 0 else 0)
        if d <= 1 or n == 0 or k_star == 0:
            return float("inf")
        return max(0.0, a - k_star) * d / (n * math.log(d))

    ranked = sorted(scan_with_forced, key=predicted_c_asymptotic)
    top_blocks = ranked[: args.top_blocks]
    print(f"  Selected top {len(top_blocks)} blocks for sweep (by predicted asymptotic c)")
    for r in top_blocks[:10]:
        print(f"    block#{r['block_id']} n={r['n']} α={r['alpha']} |S|={r['num_forced']} "
              f"d={r['d_max']} pred_c={predicted_c_asymptotic(r):.3f} "
              f"tri_free={r['is_triangle_free']}")

    # --- Step 2/3: single-type sweep ---
    print("\nSingle-type sweep...")
    all_single = []
    block_best_c = {}
    for i, rec in enumerate(top_blocks):
        series = evaluate_single_type_sweep(rec, args.k_max, timeout=args.timeout,
                                            verify_alpha=True)
        all_single.extend(series)
        if series:
            best = min(series, key=lambda r: r["c"] if r["c"] is not None else float("inf"))
            block_best_c[rec["block_id"]] = best["c"]
        if (i + 1) % 10 == 0 or i == len(top_blocks) - 1:
            print(f"  [{i+1}/{len(top_blocks)}] elapsed {time.time()-t0:.1f}s, "
                  f"{len(all_single)} datapoints")

    # --- Step 3 (mixed) ---
    print("\nMixed-type greedy sweep...")
    # Use blocks of size >= 4 with forced vertices; take pool-size per size from ranked list.
    pool_by_size = defaultdict(list)
    for r in ranked:
        if r["num_forced"] > 0 and r["n"] >= 4:
            pool_by_size[r["n"]].append(r)
    pool = []
    for n in sorted(pool_by_size):
        pool.extend(pool_by_size[n][: args.pool_size])
    print(f"  Mixed pool size: {len(pool)}")

    mixed_results = greedy_mixed_sweep(pool, args.mixed_N, beam_size=6,
                                       verify_alpha=True, timeout=args.timeout)

    # --- Save construction_results.csv ---
    cons_csv = os.path.join(OUTDIR, "construction_results.csv")
    with open(cons_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "construction", "N", "num_blocks", "num_matching",
            "predicted_alpha", "actual_alpha", "alpha_gap",
            "d_max", "c", "k4_free", "block_ids", "k_copies", "g6",
        ])
        for r in all_single:
            w.writerow([
                r["construction"], r["N"], 1, r["num_matching"],
                r["predicted_alpha"], r["actual_alpha"], r["alpha_gap"],
                r["d_max"], r["c"], int(r["k4_free"]),
                r["block_id"], r["k_copies"], r["g6"],
            ])
        for r in mixed_results:
            w.writerow([
                r["construction"], r["N"], r["num_blocks"], r["num_matching"],
                r["predicted_alpha"], r["actual_alpha"], r["alpha_gap"],
                r["d_max"], r["c"], int(r["k4_free"]),
                "|".join(str(x) for x in r["block_ids"]), "", r["g6"],
            ])
    print(f"  Wrote {cons_csv}")

    # --- Step 4: baselines ---
    sat_opt = load_sat_optimal_map(max_n=35)
    print(f"\nSAT-optimal benchmarks loaded for N in "
          f"{min(sat_opt) if sat_opt else '∅'}..{max(sat_opt) if sat_opt else '∅'}")

    # --- Step 5: stress tests ---
    print("\nStress tests...")
    # Pick a block with ≥2 forced vertices and at least 2 alpha for reuse test
    stress_out = {"reuse_tests": [], "nonforced_tests": []}
    reuse_candidates = [r for r in top_blocks if r["num_forced"] >= 1 and r["alpha"] >= 2][:5]
    for rec in reuse_candidates:
        stress_out["reuse_tests"].append(stress_reuse_forced(rec))

    nonforced_candidates = [r for r in top_blocks if r["num_forced"] >= 1 and r["n"] - r["num_forced"] >= 1][:5]
    for rec in nonforced_candidates:
        res = stress_nonforced_endpoints(rec)
        if res is not None:
            stress_out["nonforced_tests"].append(res)

    # Also tabulate alpha_gap distribution over successful constructions
    gaps = [r["alpha_gap"] for r in all_single + mixed_results]
    stress_out["alpha_gap_distribution"] = {
        "n": len(gaps),
        "mean": float(np.mean(gaps)) if gaps else 0.0,
        "max": int(max(gaps)) if gaps else 0,
        "min": int(min(gaps)) if gaps else 0,
        "zero_fraction": float(sum(1 for g in gaps if g == 0) / len(gaps)) if gaps else 0.0,
    }

    stress_path = os.path.join(OUTDIR, "stress_tests.json")
    with open(stress_path, "w") as f:
        json.dump(stress_out, f, indent=2)
    print(f"  Wrote {stress_path}")
    print(f"  α gap distribution: mean={stress_out['alpha_gap_distribution']['mean']:.2f}, "
          f"max={stress_out['alpha_gap_distribution']['max']}, "
          f"zero_fraction={stress_out['alpha_gap_distribution']['zero_fraction']:.2f}")

    # --- Step 6: plots ---
    print("\nPlots...")
    plot_tradeoff(scan_with_forced, block_best_c,
                  os.path.join(OUTDIR, "tradeoff_plot.png"))
    plot_c_vs_n(all_single, mixed_results, sat_opt,
                os.path.join(OUTDIR, "c_vs_N.png"),
                random_baseline=1.15)
    print(f"  Wrote tradeoff_plot.png, c_vs_N.png")

    # --- Summary.md ---
    summary_md = os.path.join(OUTDIR, "summary.md")
    best_single = min((r for r in all_single if r["c"] is not None),
                      key=lambda r: r["c"], default=None)
    best_mixed = min((r for r in mixed_results if r["c"] is not None),
                     key=lambda r: r["c"], default=None)
    best_overall = min([x for x in [best_single, best_mixed] if x is not None],
                       key=lambda r: r["c"], default=None)

    lines = [
        "# Forced-Matching Construction — Results",
        "",
        f"- Library blocks scanned: {len(library)}",
        f"- Blocks with ≥1 α-forced vertex: {len(scan_with_forced)}",
        f"- Single-type datapoints: {len(all_single)}",
        f"- Mixed datapoints: {len(mixed_results)}",
        "",
        "## Linear signal verification",
        "",
        f"- α gap distribution over {stress_out['alpha_gap_distribution']['n']} constructions: "
        f"mean={stress_out['alpha_gap_distribution']['mean']:.2f}, "
        f"max={stress_out['alpha_gap_distribution']['max']}, "
        f"zero-gap fraction={stress_out['alpha_gap_distribution']['zero_fraction']:.2f}",
        "",
        "  - alpha_gap = actual_α − predicted_α. If the -1 accounting is exact, all gaps are 0.",
        "  - Positive gap ⇒ predicted α is an underestimate (actual graph has larger IS),",
        "    so the -|M| count overstates α drop in some cases.",
        "",
    ]

    if best_single:
        lines += [
            "## Best single-type result",
            f"- block_id {best_single['block_id']} (n={best_single['block_n']}, "
            f"α={best_single['block_alpha']}, |S|={best_single['block_forced']})",
            f"- k={best_single['k_copies']} copies → N={best_single['N']}",
            f"- α (actual)={best_single['actual_alpha']}, "
            f"predicted={best_single['predicted_alpha']}",
            f"- d_max={best_single['d_max']}, c={best_single['c']}",
            "",
        ]
    if best_mixed:
        lines += [
            "## Best mixed result",
            f"- N={best_mixed['N']}, block sizes {best_mixed['block_sizes']}, "
            f"α (actual)={best_mixed['actual_alpha']} (pred {best_mixed['predicted_alpha']}), "
            f"d={best_mixed['d_max']}, c={best_mixed['c']}",
            "",
        ]
    if best_overall:
        lines += ["## Best overall", f"- c = {best_overall['c']} at N={best_overall['N']}", ""]

    # Baseline comparison table for N present in both
    lines += ["## Comparison vs SAT-optimal", "",
              "| N | SAT-opt c | forced-matching best c | gap |",
              "|---|-----------|------------------------|-----|"]
    by_N_single = defaultdict(list)
    for r in all_single:
        by_N_single[r["N"]].append(r)
    by_N_mixed = {r["N"]: r for r in mixed_results}
    all_N = sorted(set(list(by_N_single.keys()) + list(by_N_mixed.keys())))
    for N in all_N:
        cands = [r["c"] for r in by_N_single.get(N, []) if r["c"] is not None]
        if N in by_N_mixed and by_N_mixed[N]["c"] is not None:
            cands.append(by_N_mixed[N]["c"])
        if not cands:
            continue
        best_c = min(cands)
        sat_c = sat_opt.get(N, {}).get("c")
        gap = f"{best_c - sat_c:+.4f}" if sat_c is not None else "—"
        sat_str = f"{sat_c:.4f}" if sat_c is not None else "—"
        lines.append(f"| {N} | {sat_str} | {best_c:.4f} | {gap} |")

    lines += [
        "",
        "## Stress tests",
        "",
        "See `stress_tests.json` for full data.",
        "",
    ]
    if stress_out["reuse_tests"]:
        lines += ["### Reusing one forced vertex for two cross-edges",
                  "",
                  "| block_id | predicted if drop=1 | predicted naive (drop=2) | actual |",
                  "|---|---|---|---|"]
        for t in stress_out["reuse_tests"]:
            if t is None: continue
            lines.append(
                f"| {t['block_id']} | {t['predicted_alpha_if_counted_once']} | "
                f"{t['predicted_alpha_naive_sum']} | {t['actual_alpha']} |"
            )
        lines += ["",
                  "Interpretation: if actual matches `predicted if drop=1`, the -1 accounting",
                  "only applies once per forced vertex used. Reusing a vertex does NOT double-count.",
                  ""]

    if stress_out["nonforced_tests"]:
        lines += ["### Non-forced endpoint in matching",
                  "",
                  "| block_id | both-forced pred | both-forced actual | mixed pred | mixed actual |",
                  "|---|---|---|---|---|"]
        for t in stress_out["nonforced_tests"]:
            lines.append(
                f"| {t['block_id']} | {t['predicted_alpha_both_forced']} | "
                f"{t['actual_alpha_both_forced']} | {t['predicted_alpha_mixed']} | "
                f"{t['actual_alpha_mixed']} |"
            )
        lines += ["",
                  "Interpretation: if mixed-actual is strictly higher than both-forced-actual,",
                  "non-forced endpoints fail to cost a full -1 in α.",
                  ""]

    lines += [
        "## Key findings",
        "",
        "- Does this construction beat the random baseline (~1.15)?",
        f"  → best overall c = {best_overall['c'] if best_overall else 'N/A'}",
        "- Does it approach SAT-optimal (~0.72)?",
        f"  → gap = see table above",
        "- Is the linear signal real?",
        f"  → {stress_out['alpha_gap_distribution']['zero_fraction']:.2%} of constructions "
        f"hit predicted α exactly; max gap = {stress_out['alpha_gap_distribution']['max']}",
        "",
        f"_Total runtime: {time.time()-t0:.1f}s_",
    ]

    with open(summary_md, "w") as f:
        f.write("\n".join(lines))
    print(f"  Wrote {summary_md}")

    # --- Save all results JSON too for downstream ---
    dump_path = os.path.join(OUTDIR, "results.json")
    with open(dump_path, "w") as f:
        json.dump({
            "single": all_single,
            "mixed": mixed_results,
            "sat_optimal": sat_opt,
            "stress_tests": stress_out,
        }, f, indent=2, default=str)
    print(f"  Wrote {dump_path}")

    print(f"\nDone in {time.time()-t0:.1f}s.")


if __name__ == "__main__":
    main()
