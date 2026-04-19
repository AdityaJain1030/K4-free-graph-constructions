#!/usr/bin/env python3
"""
Greedy Reachability Experiment for K₄-Free Graphs
===================================================
Tests whether SAT-optimal graphs are reachable by greedy edge addition
with K₄-freeness checking, and how robust the construction is to
imperfect edge-ordering heuristics.

Test 1: Monotone reachability (theory sanity check)
Test 2: Oracle priority (perfect knowledge)
Test 3: Noisy oracle (robustness to imprecision)
Test 4: Structural comparison (SAT-optimal vs best heuristic)

Usage
-----
  micromamba run -n funsearch python experiments/reachability/run_experiment.py
"""

import argparse
import importlib.util
import json
import math
import os
import random
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.stdout.reconfigure(line_buffering=True)

# ============================================================================
# Import from sibling experiments via importlib (avoids module name collision)
# ============================================================================

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

_HERE = os.path.dirname(os.path.abspath(__file__))

_bd = _load_module(
    "block_decomp",
    os.path.join(_HERE, "..", "block_decomposition", "run_experiment.py"),
)
_sc = _load_module(
    "selective_cross",
    os.path.join(_HERE, "..", "selective_crossedge", "run_experiment.py"),
)

# Core functions from block_decomposition
alpha_exact = _bd.alpha_exact
alpha_sat = _bd.alpha_sat
is_k4_free = _bd.is_k4_free
graph6_to_adj = _bd.graph6_to_adj
adj_to_graph6 = _bd.adj_to_graph6
compute_c_value = _bd.compute_c_value
canonical_cert = _bd.canonical_cert

# Functions from selective_crossedge
would_create_k4 = _sc.would_create_k4
compute_nbr_masks = _sc.compute_nbr_masks
select_block_from_library = _sc.select_block_from_library
compose_selective = _sc.compose_selective
load_library = _sc.load_library

# ============================================================================
# Constants
# ============================================================================

OUTDIR = _HERE
PLOT_DIR = os.path.join(OUTDIR, "plots")
PARETO_DIR = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "reference", "pareto")
)


# ============================================================================
# Data loading
# ============================================================================

def edges_to_adj(n, edges):
    """Convert edge list [[u,v],...] to numpy bool adjacency matrix."""
    adj = np.zeros((n, n), dtype=np.bool_)
    for u, v in edges:
        adj[u, v] = adj[v, u] = True
    return adj


def load_pareto_entries(n):
    """Load pareto entries with non-null c_log for a given N."""
    path = os.path.join(PARETO_DIR, f"pareto_n{n}.json")
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        data = json.load(f)
    return [e for e in data.get("pareto_frontier", []) if e.get("c_log") is not None]


def load_all_pareto():
    """Load pareto entries for all available N values."""
    result = {}
    for n in range(12, 36):
        entries = load_pareto_entries(n)
        if entries:
            result[n] = entries
    return result


# ============================================================================
# Test 1: Monotone reachability
# ============================================================================

def test_monotone_reachability(all_pareto, num_shuffles=100):
    """Test that every SAT-optimal graph is reachable in any edge order.
    K₄-free is monotone decreasing, so no edge of a K₄-free graph
    should ever be rejected by the incremental K₄ check."""
    print("\n" + "=" * 60)
    print("TEST 1: Monotone Reachability")
    print("=" * 60)

    results = []
    total_entries = sum(len(v) for v in all_pareto.values())
    print(f"  Testing {total_entries} pareto entries across N={min(all_pareto)}..{max(all_pareto)}")
    print(f"  {num_shuffles} random edge orderings each\n")

    for n in sorted(all_pareto.keys()):
        for entry in all_pareto[n]:
            edges = [(e[0], e[1]) for e in entry["edges"]]
            num_edges = len(edges)

            # Pre-check: target is K4-free
            target_adj = edges_to_adj(n, edges)
            assert is_k4_free(target_adj), f"Target N={n} α={entry['alpha']} not K4-free!"

            all_accepted_flag = True
            max_rejected = 0

            for seed in range(num_shuffles):
                rng = random.Random(seed)
                shuffled = list(edges)
                rng.shuffle(shuffled)

                adj = np.zeros((n, n), dtype=np.bool_)
                nbr_masks = [0] * n
                rejected = 0

                for u, v in shuffled:
                    if would_create_k4(adj, nbr_masks, u, v):
                        rejected += 1
                    else:
                        adj[u, v] = adj[v, u] = True
                        nbr_masks[u] |= (1 << v)
                        nbr_masks[v] |= (1 << u)

                if rejected > 0:
                    all_accepted_flag = False
                max_rejected = max(max_rejected, rejected)

            status = "PASS" if all_accepted_flag else "FAIL"
            results.append({
                "n": n,
                "alpha": entry["alpha"],
                "d_max": entry["d_max"],
                "c_log": entry["c_log"],
                "num_edges": num_edges,
                "num_shuffles": num_shuffles,
                "all_accepted": all_accepted_flag,
                "max_rejected": max_rejected,
            })

            print(f"  N={n:2d}  α={entry['alpha']:2d}  d={entry['d_max']:2d}  "
                  f"edges={num_edges:3d}  → {status}  (max_rejected={max_rejected})")

    passed = sum(1 for r in results if r["all_accepted"])
    print(f"\n  Summary: {passed}/{len(results)} entries passed (all edges accepted in all orderings)")

    return results


# ============================================================================
# Test 2: Oracle priority
# ============================================================================

def test_oracle_priority(n, entries):
    """Test greedy construction with perfect knowledge of target edges."""
    print("\n" + "=" * 60)
    print("TEST 2: Oracle Priority")
    print("=" * 60)

    all_possible = [(i, j) for i in range(n) for j in range(i + 1, n)]
    results = []

    for entry in entries:
        target_set = set((min(u, v), max(u, v)) for u, v in entry["edges"])
        d_cap = entry["d_max"]

        # Sort: target edges first, then non-target; stable lexicographic tie-break
        edge_order = sorted(all_possible, key=lambda e: (0 if e in target_set else 1, e))

        adj = np.zeros((n, n), dtype=np.bool_)
        nbr_masks = [0] * n
        degrees = np.zeros(n, dtype=np.int32)
        accepted = set()
        skipped_k4 = []
        skipped_dcap = []

        for u, v in edge_order:
            if degrees[u] >= d_cap or degrees[v] >= d_cap:
                skipped_dcap.append((u, v))
                continue
            if would_create_k4(adj, nbr_masks, u, v):
                skipped_k4.append((u, v))
                continue
            adj[u, v] = adj[v, u] = True
            nbr_masks[u] |= (1 << v)
            nbr_masks[v] |= (1 << u)
            degrees[u] += 1
            degrees[v] += 1
            accepted.add((u, v))

        missing = target_set - accepted
        extra = accepted - target_set
        d_max_result = int(degrees.max())
        alpha_result = alpha_exact(adj)[0]
        c_result = compute_c_value(alpha_result, n, d_max_result)

        exact = len(missing) == 0 and len(extra) == 0

        result = {
            "n": n,
            "alpha_target": entry["alpha"],
            "d_max_target": entry["d_max"],
            "c_target": entry["c_log"],
            "target_edges": len(target_set),
            "edges_accepted": len(accepted),
            "edges_missing": len(missing),
            "extra_edges": len(extra),
            "skipped_k4": len(skipped_k4),
            "skipped_dcap": len(skipped_dcap),
            "exact_recovery": exact,
            "alpha_result": int(alpha_result),
            "d_max_result": d_max_result,
            "c_result": round(c_result, 4) if c_result != float("inf") else None,
            "degree_sequence": sorted(degrees.tolist(), reverse=True),
            "missing_edges": sorted(missing),
            "extra_edge_list": sorted(extra),
        }
        results.append(result)

        status = "EXACT" if exact else f"MISMATCH (-{len(missing)} +{len(extra)})"
        print(f"  α={entry['alpha']}, d={entry['d_max']}: target={len(target_set)} edges → "
              f"{status}  result: α={alpha_result}, d={d_max_result}, c={c_result:.4f}")
        if skipped_k4:
            # These should be non-target edges only
            in_target = [e for e in skipped_k4 if e in target_set]
            print(f"    K4-skipped: {len(skipped_k4)} ({len(in_target)} were target edges)")
        if skipped_dcap:
            in_target_dc = [e for e in skipped_dcap if e in target_set]
            print(f"    d_cap-skipped: {len(skipped_dcap)} ({len(in_target_dc)} were target edges)")

    return results


# ============================================================================
# Test 3: Noisy oracle
# ============================================================================

def test_noisy_oracle(n, entry, epsilons, num_seeds=50):
    """Test greedy with noisy oracle: priority flipped with probability ε."""
    print("\n" + "=" * 60)
    print("TEST 3: Noisy Oracle")
    print("=" * 60)
    print(f"  Target: N={n}, α={entry['alpha']}, d_max={entry['d_max']}, c={entry['c_log']}")

    target_set = set((min(u, v), max(u, v)) for u, v in entry["edges"])
    d_cap = entry["d_max"]
    all_possible = [(i, j) for i in range(n) for j in range(i + 1, n)]

    results_by_eps = {}

    for eps in epsilons:
        trials = []

        for seed in range(num_seeds):
            rng = random.Random(seed)

            # Assign priorities with noise
            priorities = {}
            for e in all_possible:
                base = 0 if e in target_set else 1
                if rng.random() < eps:
                    base = 1 - base
                priorities[e] = base

            # Sort by priority, random tie-break
            tie_break = {e: rng.random() for e in all_possible}
            edge_order = sorted(all_possible, key=lambda e: (priorities[e], tie_break[e]))

            # Greedy add
            adj = np.zeros((n, n), dtype=np.bool_)
            nbr_masks = [0] * n
            degrees = np.zeros(n, dtype=np.int32)
            accepted = set()

            for u, v in edge_order:
                if degrees[u] >= d_cap or degrees[v] >= d_cap:
                    continue
                if would_create_k4(adj, nbr_masks, u, v):
                    continue
                adj[u, v] = adj[v, u] = True
                nbr_masks[u] |= (1 << v)
                nbr_masks[v] |= (1 << u)
                degrees[u] += 1
                degrees[v] += 1
                accepted.add((u, v))

            alpha_val = alpha_exact(adj)[0]
            d_max_r = int(degrees.max())
            c_val = compute_c_value(alpha_val, n, d_max_r)

            trials.append({
                "seed": seed,
                "exact_recovery": accepted == target_set,
                "alpha": int(alpha_val),
                "d_max": d_max_r,
                "c": round(c_val, 4) if c_val != float("inf") else None,
                "edges_recovered": len(target_set & accepted),
                "edges_missing": len(target_set - accepted),
                "extra_edges": len(accepted - target_set),
            })

        cs = [t["c"] for t in trials if t["c"] is not None]
        recovery_rate = sum(1 for t in trials if t["exact_recovery"]) / num_seeds

        results_by_eps[str(eps)] = {
            "epsilon": eps,
            "num_seeds": num_seeds,
            "recovery_rate": round(recovery_rate, 4),
            "mean_c": round(float(np.mean(cs)), 4) if cs else None,
            "min_c": round(min(cs), 4) if cs else None,
            "max_c": round(max(cs), 4) if cs else None,
            "std_c": round(float(np.std(cs)), 4) if cs else None,
            "mean_missing": round(float(np.mean([t["edges_missing"] for t in trials])), 2),
            "mean_extra": round(float(np.mean([t["extra_edges"] for t in trials])), 2),
            "trials": trials,
        }

        print(f"  ε={eps:.2f}: recovery={recovery_rate:.0%}, "
              f"mean_c={np.mean(cs):.4f} ± {np.std(cs):.4f}, "
              f"min_c={min(cs):.4f}")

    return results_by_eps


# ============================================================================
# Test 4: Structural comparison
# ============================================================================

def test_structural_comparison(n, sat_entry):
    """Compare SAT-optimal N=16 graph with best selective_crossedge graph."""
    print("\n" + "=" * 60)
    print("TEST 4: Structural Comparison")
    print("=" * 60)

    # 1. Build SAT-optimal graph
    sat_adj = edges_to_adj(n, sat_entry["edges"])
    sat_edges = set((min(u, v), max(u, v)) for u, v in sat_entry["edges"])

    # 2. Reconstruct selective_crossedge best graph
    # Best result: config=[4,3,3,3,3], strategy=random, p=1.0, d_cap=6, seed=15
    library = load_library()

    trial_rng = random.Random(15)
    block_sizes = [4, 3, 3, 3, 3]
    blocks = []
    for s in block_sizes:
        blocks.append(select_block_from_library(library, s, trial_rng))

    sc_adj, sc_stats = compose_selective(
        blocks, "random", d_cap=6, target_alpha=None, p=1.0, seed=15
    )

    print(f"  Reconstructed selective_crossedge graph: "
          f"α={sc_stats['alpha']}, d_max={sc_stats['d_max']}, c={sc_stats['c']}")

    # 3. Extract edge sets
    sc_edges = set()
    for i in range(n):
        for j in range(i + 1, n):
            if sc_adj[i, j]:
                sc_edges.add((i, j))

    # 4. Compare edges
    overlap = sat_edges & sc_edges
    only_sat = sat_edges - sc_edges
    only_sc = sc_edges - sat_edges
    union = sat_edges | sc_edges
    jaccard = len(overlap) / len(union) if union else 0.0

    # 5. Isomorphism check
    sat_cert = canonical_cert(sat_adj)
    sc_cert = canonical_cert(sc_adj)
    is_iso = (sat_cert == sc_cert)

    # 6. Degree sequences
    sat_deg = sorted([int(sat_adj[i].sum()) for i in range(n)], reverse=True)
    sc_deg = sorted([int(sc_adj[i].sum()) for i in range(n)], reverse=True)

    # 7. Alpha
    sat_alpha = alpha_exact(sat_adj)[0]
    sc_alpha = alpha_exact(sc_adj)[0]

    result = {
        "sat_optimal": {
            "alpha": int(sat_alpha),
            "d_max": sat_entry["d_max"],
            "c": sat_entry["c_log"],
            "num_edges": len(sat_edges),
            "degree_sequence": sat_deg,
            "g6": sat_entry.get("g6"),
        },
        "selective_crossedge": {
            "alpha": int(sc_alpha),
            "d_max": sc_stats["d_max"],
            "c": sc_stats["c"],
            "num_edges": len(sc_edges),
            "degree_sequence": sc_deg,
            "config": "4+3+3+3+3",
            "seed": 15,
        },
        "comparison": {
            "edge_overlap": len(overlap),
            "jaccard_similarity": round(jaccard, 4),
            "symmetric_difference": len(only_sat) + len(only_sc),
            "only_in_sat": len(only_sat),
            "only_in_sc": len(only_sc),
            "is_isomorphic": is_iso,
            "same_degree_sequence": sat_deg == sc_deg,
            "same_alpha": int(sat_alpha) == int(sc_alpha),
        },
    }

    print(f"\n  SAT-optimal:  α={sat_alpha}, d_max={sat_entry['d_max']}, "
          f"edges={len(sat_edges)}, deg={sat_deg}")
    print(f"  Selective CE: α={sc_alpha}, d_max={sc_stats['d_max']}, "
          f"edges={len(sc_edges)}, deg={sc_deg}")
    print(f"\n  Edge overlap: {len(overlap)} / {len(union)} "
          f"(Jaccard={jaccard:.4f})")
    print(f"  Only in SAT-optimal: {len(only_sat)}")
    print(f"  Only in selective CE: {len(only_sc)}")
    print(f"  Symmetric difference: {len(only_sat) + len(only_sc)}")
    print(f"  Isomorphic: {is_iso}")

    return result


# ============================================================================
# Plotting
# ============================================================================

def plot_test1(results):
    """Bar chart confirming monotone reachability."""
    fig, ax = plt.subplots(figsize=(12, 5))

    labels = [f"N={r['n']}\nα={r['alpha']}" for r in results]
    colors = ["#44cc88" if r["all_accepted"] else "#cc4444" for r in results]
    x = range(len(results))

    ax.bar(x, [r["num_edges"] for r in results], color=colors, alpha=0.7)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=45, ha="right")
    ax.set_ylabel("Number of edges", fontsize=11)
    ax.set_title("Test 1: Monotone Reachability (green = all edges accepted in all orderings)", fontsize=13)
    ax.grid(True, alpha=0.3, axis="y")

    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "test1_monotone.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


def plot_test3(results_by_eps, c_target):
    """Noise degradation plot: ε → c and recovery rate."""
    epsilons = sorted(float(k) for k in results_by_eps.keys())
    mean_cs = [results_by_eps[str(e)]["mean_c"] for e in epsilons]
    std_cs = [results_by_eps[str(e)]["std_c"] for e in epsilons]
    recovery = [results_by_eps[str(e)]["recovery_rate"] for e in epsilons]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    color1 = "#2266cc"
    ax1.errorbar(epsilons, mean_cs, yerr=std_cs, fmt="o-", color=color1,
                 linewidth=2, markersize=8, capsize=5, label="Mean c")
    ax1.axhline(y=c_target, color="gold", linestyle="--", linewidth=2,
                label=f"SAT-optimal (c={c_target})")
    ax1.axhline(y=0.90, color="purple", linestyle=":", linewidth=1.5,
                label="IS-join baseline (~0.90)")
    ax1.set_xlabel("Noise level (ε)", fontsize=12)
    ax1.set_ylabel("c = α·d_max / (N·ln d_max)", fontsize=12, color=color1)
    ax1.tick_params(axis="y", labelcolor=color1)

    ax2 = ax1.twinx()
    color2 = "#cc4444"
    ax2.plot(epsilons, recovery, "s--", color=color2, linewidth=2,
             markersize=8, label="Recovery rate")
    ax2.set_ylabel("Exact recovery rate", fontsize=12, color=color2)
    ax2.tick_params(axis="y", labelcolor=color2)
    ax2.set_ylim(-0.05, 1.05)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10, loc="upper left")

    ax1.set_title("Test 3: Noisy Oracle — Degradation with Noise (N=16, α=4, d=4)", fontsize=13)
    ax1.grid(True, alpha=0.3)

    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "test3_noise_degradation.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


def plot_test4(result):
    """Degree sequence comparison plot."""
    fig, ax = plt.subplots(figsize=(10, 6))

    sat_deg = result["sat_optimal"]["degree_sequence"]
    sc_deg = result["selective_crossedge"]["degree_sequence"]
    n = len(sat_deg)

    ax.plot(range(n), sat_deg, "o-", color="#cc8800", linewidth=2, markersize=8,
            label=f"SAT-optimal (c={result['sat_optimal']['c']:.4f}, "
                  f"α={result['sat_optimal']['alpha']}, d={result['sat_optimal']['d_max']})")
    ax.plot(range(n), sc_deg, "s-", color="#2266cc", linewidth=2, markersize=8,
            label=f"Selective CE (c={result['selective_crossedge']['c']}, "
                  f"α={result['selective_crossedge']['alpha']}, "
                  f"d={result['selective_crossedge']['d_max']})")

    ax.set_xlabel("Vertex (sorted by degree)", fontsize=12)
    ax.set_ylabel("Degree", fontsize=12)
    ax.set_title("Test 4: Degree Sequence Comparison (N=16)", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, alpha=0.3)

    # Add annotation with edge overlap stats
    comp = result["comparison"]
    info = (f"Edge overlap: {comp['edge_overlap']}\n"
            f"Jaccard: {comp['jaccard_similarity']:.3f}\n"
            f"Sym. diff: {comp['symmetric_difference']}\n"
            f"Isomorphic: {comp['is_isomorphic']}")
    ax.text(0.98, 0.02, info, transform=ax.transAxes, fontsize=9,
            verticalalignment="bottom", horizontalalignment="right",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="lightyellow", alpha=0.8))

    fig.tight_layout()
    path = os.path.join(PLOT_DIR, "test4_degree_sequences.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"  Saved {path}")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Greedy reachability experiment for K4-free graphs"
    )
    parser.add_argument("--test", type=int, nargs="+", default=[1, 2, 3, 4],
                        help="Which tests to run (default: 1 2 3 4)")
    parser.add_argument("--shuffles", type=int, default=100,
                        help="Shuffle orderings for Test 1 (default: 100)")
    parser.add_argument("--noisy-seeds", type=int, default=50,
                        help="Seeds per noise level for Test 3 (default: 50)")
    args = parser.parse_args()

    os.makedirs(PLOT_DIR, exist_ok=True)

    all_results = {}
    t0_total = time.time()

    # === Test 1: Monotone Reachability ===
    if 1 in args.test:
        t0 = time.time()
        all_pareto = load_all_pareto()
        print(f"Loaded pareto data for {len(all_pareto)} N values "
              f"({sum(len(v) for v in all_pareto.values())} total entries)")

        results_1 = test_monotone_reachability(all_pareto, num_shuffles=args.shuffles)
        all_results["test1_monotone"] = results_1

        with open(os.path.join(OUTDIR, "results_test1.json"), "w") as f:
            json.dump(results_1, f, indent=2)
        print(f"  Test 1 completed in {time.time() - t0:.1f}s")

        plot_test1(results_1)

    # === Test 2: Oracle Priority ===
    if 2 in args.test:
        t0 = time.time()
        entries_16 = load_pareto_entries(16)
        print(f"\nLoaded {len(entries_16)} N=16 pareto entries")

        results_2 = test_oracle_priority(16, entries_16)
        all_results["test2_oracle"] = results_2

        with open(os.path.join(OUTDIR, "results_test2.json"), "w") as f:
            json.dump(results_2, f, indent=2)
        print(f"  Test 2 completed in {time.time() - t0:.1f}s")

    # === Test 3: Noisy Oracle ===
    if 3 in args.test:
        t0 = time.time()
        entries_16 = load_pareto_entries(16)
        # Target: the α=4, d_max=4 entry (most interesting, same c as α=3/d=8)
        target = next(
            (e for e in entries_16 if e["alpha"] == 4 and e["d_max"] == 4), None
        )
        if target is None:
            print("\n  WARNING: N=16 α=4 d=4 entry not found, skipping Test 3")
        else:
            epsilons = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5]
            results_3 = test_noisy_oracle(
                16, target, epsilons, num_seeds=args.noisy_seeds
            )
            all_results["test3_noisy"] = results_3

            # Save without per-trial details for the summary
            with open(os.path.join(OUTDIR, "results_test3.json"), "w") as f:
                json.dump(results_3, f, indent=2)
            print(f"  Test 3 completed in {time.time() - t0:.1f}s")

            plot_test3(results_3, c_target=target["c_log"])

    # === Test 4: Structural Comparison ===
    if 4 in args.test:
        t0 = time.time()
        entries_16 = load_pareto_entries(16)
        target = next(
            (e for e in entries_16 if e["alpha"] == 4 and e["d_max"] == 4), None
        )
        if target is None:
            print("\n  WARNING: N=16 α=4 d=4 entry not found, skipping Test 4")
        else:
            results_4 = test_structural_comparison(16, target)
            all_results["test4_structural"] = results_4

            with open(os.path.join(OUTDIR, "results_test4.json"), "w") as f:
                json.dump(results_4, f, indent=2)
            print(f"  Test 4 completed in {time.time() - t0:.1f}s")

            plot_test4(results_4)

    # === Save combined summary ===
    summary = {
        "total_time_s": round(time.time() - t0_total, 1),
        "tests_run": args.test,
    }
    if "test1_monotone" in all_results:
        r1 = all_results["test1_monotone"]
        summary["test1"] = {
            "total_entries": len(r1),
            "all_passed": all(r["all_accepted"] for r in r1),
            "any_failures": [r for r in r1 if not r["all_accepted"]],
        }
    if "test2_oracle" in all_results:
        summary["test2"] = all_results["test2_oracle"]
    if "test3_noisy" in all_results:
        r3 = all_results["test3_noisy"]
        summary["test3"] = {
            eps: {k: v for k, v in data.items() if k != "trials"}
            for eps, data in r3.items()
        }
    if "test4_structural" in all_results:
        summary["test4"] = all_results["test4_structural"]

    with open(os.path.join(OUTDIR, "experiment_summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    # === Final Summary ===
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"  Total time: {time.time() - t0_total:.1f}s")

    if "test1_monotone" in all_results:
        r1 = all_results["test1_monotone"]
        passed = sum(1 for r in r1 if r["all_accepted"])
        print(f"\n  Test 1 (Monotone): {passed}/{len(r1)} passed")
        if passed == len(r1):
            print("    → K₄-free monotonicity CONFIRMED: every SAT-optimal graph "
                  "is greedy-reachable in any edge order")

    if "test2_oracle" in all_results:
        print(f"\n  Test 2 (Oracle):")
        for r in all_results["test2_oracle"]:
            status = "EXACT" if r["exact_recovery"] else f"MISS({r['edges_missing']})+EXTRA({r['extra_edges']})"
            print(f"    α={r['alpha_target']}, d={r['d_max_target']}: {status}, "
                  f"result c={r['c_result']}")

    if "test3_noisy" in all_results:
        r3 = all_results["test3_noisy"]
        print(f"\n  Test 3 (Noisy Oracle):")
        for eps in sorted(float(k) for k in r3.keys()):
            d = r3[str(eps)]
            print(f"    ε={eps:.2f}: recovery={d['recovery_rate']:.0%}, "
                  f"mean_c={d['mean_c']:.4f}")

    if "test4_structural" in all_results:
        r4 = all_results["test4_structural"]
        comp = r4["comparison"]
        print(f"\n  Test 4 (Structural):")
        print(f"    Edge overlap: {comp['edge_overlap']}, "
              f"Jaccard: {comp['jaccard_similarity']:.3f}")
        print(f"    Sym. diff: {comp['symmetric_difference']}, "
              f"Isomorphic: {comp['is_isomorphic']}")

    print("\nDone.")


if __name__ == "__main__":
    main()
