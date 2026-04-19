#!/usr/bin/env python3
"""
Block Optimal Cross-Edge Experiment
====================================
Uses SAT to find the optimal cross-edge assignment between library blocks.
No heuristics — finds the true ceiling of block-based composition.

Supports 2-block pairs (N ≤ 16) and multi-block compositions (N > 16).

Usage
-----
  micromamba run -n funsearch python experiments/block_optimal/run_experiment.py
  micromamba run -n funsearch python experiments/block_optimal/run_experiment.py --n-values 16 20 24
"""

import argparse
import importlib.util
import json
import math
import os
import sys
import threading
import time
from collections import defaultdict
from itertools import combinations, product

import numpy as np
from pysat.card import CardEnc, EncType
from pysat.solvers import Glucose4

sys.stdout.reconfigure(line_buffering=True)

# ============================================================================
# Imports from sibling experiments
# ============================================================================

_HERE = os.path.dirname(os.path.abspath(__file__))


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
is_k4_free = _bd.is_k4_free
compute_c_value = _bd.compute_c_value
adj_to_graph6 = _bd.adj_to_graph6

# ============================================================================
# Constants
# ============================================================================

OUTDIR = _HERE
LIBRARY_PATH = os.path.join(
    _HERE, "..", "block_decomposition", "library.json"
)
PARETO_DIR = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "SAT_old", "pareto_reference")
)


# ============================================================================
# Data loading
# ============================================================================

def load_library():
    with open(LIBRARY_PATH) as f:
        data = json.load(f)
    lib = data if isinstance(data, list) else data.get("blocks", data.get("library", []))
    return lib


def load_sat_optimal(N):
    path = os.path.join(PARETO_DIR, f"pareto_n{N}.json")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        data = json.load(f)
    frontier = [e for e in data.get("pareto_frontier", []) if e.get("c_log") is not None]
    if not frontier:
        return None
    best = min(frontier, key=lambda e: e["c_log"])
    return {"alpha": best["alpha"], "d_max": best["d_max"], "c": best["c_log"]}


# ============================================================================
# Block selection and precomputation
# ============================================================================

def select_blocks(library, max_per_group=3, max_per_size=20):
    """Select representative blocks per size, grouped by (alpha, d_max)."""
    by_size = defaultdict(list)
    for b in library:
        by_size[b["n"]].append(b)

    selected = {}
    for n in sorted(by_size.keys()):
        blocks = by_size[n]
        if n <= 5:
            selected[n] = blocks
        else:
            groups = defaultdict(list)
            for b in blocks:
                groups[(b["alpha"], b["d_max"])].append(b)
            result = []
            for key in sorted(groups.keys()):
                result.extend(groups[key][:max_per_group])
                if len(result) >= max_per_size:
                    break
            selected[n] = result[:max_per_size]
    return selected


def block_to_adj(block):
    n = block["n"]
    adj = np.zeros((n, n), dtype=np.bool_)
    for u, v in block["edges"]:
        adj[u, v] = adj[v, u] = True
    return adj


def enumerate_triangles(adj):
    n = adj.shape[0]
    tris = []
    for i in range(n):
        for j in range(i + 1, n):
            if not adj[i, j]:
                continue
            for k in range(j + 1, n):
                if adj[i, k] and adj[j, k]:
                    tris.append((i, j, k))
    return tris


def enumerate_is_by_size(adj):
    """Return dict: size -> list of frozensets of vertex indices."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    by_size = defaultdict(list)

    def bt(v, cur, forbidden, size):
        if size > 0:
            verts = []
            m = cur
            while m:
                bit = (m & -m).bit_length() - 1
                verts.append(bit)
                m &= m - 1
            by_size[size].append(frozenset(verts))
        for u in range(v, n):
            if not (forbidden & (1 << u)):
                bt(u + 1, cur | (1 << u), forbidden | nbr[u], size + 1)

    bt(0, 0, 0, 0)
    return dict(by_size)


def precompute_block(block):
    """Precompute structural info for a block."""
    adj = block_to_adj(block)
    return {
        "adj": adj,
        "n": block["n"],
        "alpha": block["alpha"],
        "d_max": block["d_max"],
        "block_id": block["block_id"],
        "is_by_size": enumerate_is_by_size(adj),
        "triangles": enumerate_triangles(adj),
        "edges": [(i, j) for i in range(adj.shape[0])
                  for j in range(i + 1, adj.shape[0]) if adj[i, j]],
        "internal_deg": adj.sum(axis=1).astype(int),
    }


# ============================================================================
# General multi-block SAT solver
# ============================================================================

def solve_multi_block(block_infos, target_alpha, target_d_max, timeout=30):
    """Find cross-edge assignment for K blocks satisfying K₄-free, α ≤ target, d_max ≤ target.

    Args:
        block_infos: list of precomputed block info dicts
        target_alpha: maximum independence number
        target_d_max: maximum vertex degree

    Returns:
        list of cross-edges in global indexing [(u, v), ...] or None
    """
    K = len(block_infos)
    sizes = [bi["n"] for bi in block_infos]
    N = sum(sizes)

    # Global vertex offsets
    offsets = [0]
    for s in sizes:
        offsets.append(offsets[-1] + s)

    # Quick feasibility: internal degree and alpha checks
    for bi in block_infos:
        if int(bi["internal_deg"].max()) > target_d_max:
            return None
        if bi["alpha"] > target_alpha:
            return None

    # Cross-edge variable mapping: (global_i, global_j) -> var_id
    # Only between different blocks
    var_map = {}
    next_var = 1
    for p in range(K):
        for q in range(p + 1, K):
            for i in range(sizes[p]):
                for j in range(sizes[q]):
                    gi = offsets[p] + i
                    gj = offsets[q] + j
                    var_map[(gi, gj)] = next_var
                    var_map[(gj, gi)] = next_var
                    next_var += 1

    num_cross_vars = next_var - 1
    if num_cross_vars == 0:
        return []

    solver = Glucose4()
    top_id = num_cross_vars

    try:
        # === K₄-free constraints ===

        # Type A: 3 from block p, 1 from block q
        for p in range(K):
            for q in range(K):
                if p == q:
                    continue
                for (a1, a2, a3) in block_infos[p]["triangles"]:
                    ga1 = offsets[p] + a1
                    ga2 = offsets[p] + a2
                    ga3 = offsets[p] + a3
                    for b in range(sizes[q]):
                        gb = offsets[q] + b
                        solver.add_clause([
                            -var_map[(ga1, gb)],
                            -var_map[(ga2, gb)],
                            -var_map[(ga3, gb)],
                        ])

        # Type B: 2 from block p, 2 from block q
        for p in range(K):
            for q in range(p + 1, K):
                for (a1, a2) in block_infos[p]["edges"]:
                    ga1, ga2 = offsets[p] + a1, offsets[p] + a2
                    for (b1, b2) in block_infos[q]["edges"]:
                        gb1, gb2 = offsets[q] + b1, offsets[q] + b2
                        solver.add_clause([
                            -var_map[(ga1, gb1)],
                            -var_map[(ga1, gb2)],
                            -var_map[(ga2, gb1)],
                            -var_map[(ga2, gb2)],
                        ])

        # Type C: 2 from block p, 1 from block q, 1 from block r (q < r, p ≠ q, p ≠ r)
        if K >= 3:
            for p in range(K):
                others = [x for x in range(K) if x != p]
                for qi, ri in combinations(range(len(others)), 2):
                    q, r = others[qi], others[ri]
                    for (a1, a2) in block_infos[p]["edges"]:
                        ga1, ga2 = offsets[p] + a1, offsets[p] + a2
                        for b in range(sizes[q]):
                            gb = offsets[q] + b
                            for c in range(sizes[r]):
                                gc = offsets[r] + c
                                solver.add_clause([
                                    -var_map[(ga1, gb)],
                                    -var_map[(ga2, gb)],
                                    -var_map[(ga1, gc)],
                                    -var_map[(ga2, gc)],
                                    -var_map[(gb, gc)],
                                ])

        # Type D: 1 from each of 4 distinct blocks
        if K >= 4:
            for p, q, r, s in combinations(range(K), 4):
                for a in range(sizes[p]):
                    ga = offsets[p] + a
                    for b in range(sizes[q]):
                        gb = offsets[q] + b
                        for c in range(sizes[r]):
                            gc = offsets[r] + c
                            for d in range(sizes[s]):
                                gd = offsets[s] + d
                                solver.add_clause([
                                    -var_map[(ga, gb)],
                                    -var_map[(ga, gc)],
                                    -var_map[(ga, gd)],
                                    -var_map[(gb, gc)],
                                    -var_map[(gb, gd)],
                                    -var_map[(gc, gd)],
                                ])

        # === Alpha constraint: no IS of size target_alpha + 1 ===
        k = target_alpha + 1
        alphas = [bi["alpha"] for bi in block_infos]
        is_data = [bi["is_by_size"] for bi in block_infos]

        # Generate all partitions of k across K blocks
        def gen_partitions(remaining, idx, current):
            if idx == K:
                if remaining == 0:
                    yield tuple(current)
                return
            max_s = min(remaining, alphas[idx])
            for s in range(max_s + 1):
                yield from gen_partitions(remaining - s, idx + 1, current + [s])

        for partition in gen_partitions(k, 0, []):
            nonzero = [i for i in range(K) if partition[i] > 0]
            if len(nonzero) <= 1:
                # IS entirely in one block — can't kill with cross-edges
                # Already excluded by alpha check above
                continue

            # Collect IS lists for each block
            is_lists = []
            skip = False
            for i in range(K):
                s = partition[i]
                if s == 0:
                    is_lists.append([frozenset()])
                else:
                    if s not in is_data[i]:
                        skip = True
                        break
                    is_lists.append(is_data[i][s])
            if skip:
                continue

            for is_tuple in product(*is_lists):
                # Clause: at least one cross-edge between vertices from
                # different blocks within this IS
                clause = []
                for p in range(K):
                    for q in range(p + 1, K):
                        for a in is_tuple[p]:
                            for b in is_tuple[q]:
                                ga = offsets[p] + a
                                gb = offsets[q] + b
                                v = var_map.get((ga, gb))
                                if v is not None:
                                    clause.append(v)
                if not clause:
                    return None  # Infeasible
                solver.add_clause(clause)

        # === Degree constraints ===
        for p in range(K):
            for i in range(sizes[p]):
                gi = offsets[p] + i
                int_deg = int(block_infos[p]["internal_deg"][i])
                budget = target_d_max - int_deg
                if budget < 0:
                    return None

                # Collect all cross-edge vars incident to this vertex
                lits = []
                for q in range(K):
                    if q == p:
                        continue
                    for j in range(sizes[q]):
                        gj = offsets[q] + j
                        v = var_map.get((gi, gj))
                        if v is not None:
                            lits.append(v)

                if not lits or budget >= len(lits):
                    continue

                cnf = CardEnc.atmost(lits, bound=budget, top_id=top_id,
                                     encoding=EncType.totalizer)
                top_id = cnf.nv
                for cl in cnf.clauses:
                    solver.add_clause(cl)

        # === Solve ===
        flag = [False]

        def on_timeout():
            flag[0] = True
            solver.interrupt()

        timer = threading.Timer(timeout, on_timeout)
        timer.start()
        result = solver.solve_limited()
        timer.cancel()

        if flag[0] or result is None or not result:
            return None

        # Extract cross-edges
        model_set = set(solver.get_model())
        cross_edges = []
        seen = set()
        for (gi, gj), vid in var_map.items():
            if gi < gj and vid in model_set and (gi, gj) not in seen:
                cross_edges.append((gi, gj))
                seen.add((gi, gj))
        return cross_edges

    finally:
        solver.delete()


# ============================================================================
# Binary search for minimum d_max
# ============================================================================

def find_best_for_blocks(block_infos, target_alpha, timeout=30):
    """Binary search for minimum d_max, then build and verify graph."""
    sizes = [bi["n"] for bi in block_infos]
    N = sum(sizes)
    offsets = [0]
    for s in sizes:
        offsets.append(offsets[-1] + s)

    max_internal = max(int(bi["internal_deg"].max()) for bi in block_infos)

    lo = max(max_internal, 2)
    hi = N - 1

    best_cross = None

    while lo <= hi:
        mid = (lo + hi) // 2
        cross = solve_multi_block(block_infos, target_alpha, mid, timeout=timeout)
        if cross is not None:
            best_cross = cross
            hi = mid - 1
        else:
            lo = mid + 1

    if best_cross is None:
        return None

    # Build full graph
    adj = np.zeros((N, N), dtype=np.bool_)
    for p, bi in enumerate(block_infos):
        o = offsets[p]
        adj[o:o + bi["n"], o:o + bi["n"]] = bi["adj"]
    for u, v in best_cross:
        adj[u, v] = adj[v, u] = True

    # Verify and score
    k4free = is_k4_free(adj)
    if N <= 20:
        actual_alpha = alpha_exact(adj)[0]
    else:
        actual_alpha, _, _ = alpha_sat(adj, timeout=60)
    actual_d_max = int(adj.sum(axis=1).max())
    c = compute_c_value(actual_alpha, N, actual_d_max)
    deg_seq = sorted(adj.sum(axis=1).astype(int).tolist(), reverse=True)

    return {
        "target_alpha": target_alpha,
        "actual_alpha": int(actual_alpha),
        "d_max": actual_d_max,
        "c": round(c, 4) if c != float("inf") else None,
        "num_cross_edges": len(best_cross),
        "total_edges": int(adj.sum()) // 2,
        "k4_free_verified": bool(k4free),
        "degree_sequence": deg_seq,
        "g6": adj_to_graph6(adj),
    }


# ============================================================================
# Configuration generation
# ============================================================================

def generate_size_tuples(N, min_size=3, max_size=8):
    """Generate size tuples that sum to N using blocks of min_size..max_size.
    Returns list of sorted tuples."""
    results = set()

    def recurse(remaining, parts, min_part):
        if remaining == 0:
            results.add(tuple(sorted(parts, reverse=True)))
            return
        if remaining < min_part:
            return
        for s in range(min(remaining, max_size), min_part - 1, -1):
            if s < min_size:
                break
            recurse(remaining - s, parts + [s], min_part)

    recurse(N, [], min_size)
    return sorted(results)


def generate_configs(N, selected_blocks, max_blocks=4, max_per_size_for_multi=5):
    """Generate block configurations to test for target N."""
    size_tuples = generate_size_tuples(N, min_size=3, max_size=8)

    # Filter by number of blocks
    size_tuples = [t for t in size_tuples if len(t) <= max_blocks]

    configs = []
    for st in size_tuples:
        # Check all sizes exist in selected_blocks
        if not all(s in selected_blocks for s in st):
            continue

        num_blocks = len(st)
        if num_blocks == 2:
            # For 2 blocks, use more representatives
            limit = 20
        elif num_blocks == 3:
            limit = max_per_size_for_multi
        else:
            limit = 3

        # Build block lists per position, respecting limits
        block_lists = []
        for s in st:
            block_lists.append(selected_blocks[s][:limit])

        # Enumerate combinations (avoiding duplicates for equal sizes)
        if len(set(st)) == 1 and num_blocks > 1:
            # All same size: use combinations with replacement
            combos = list(combinations(range(len(block_lists[0])), num_blocks))
            for combo in combos:
                configs.append(([block_lists[0][i] for i in combo], st))
            # Also self-combinations (same block repeated)
            for i in range(len(block_lists[0])):
                combo = tuple([i] * num_blocks)
                if combo not in [tuple(sorted(c)) for c in combos]:
                    configs.append(([block_lists[0][i]] * num_blocks, st))
        elif num_blocks == 2 and st[0] != st[1]:
            for ba in block_lists[0]:
                for bb in block_lists[1]:
                    configs.append(([ba, bb], st))
        elif num_blocks >= 3:
            # For multi-block: enumerate product but cap total
            max_combos = 200
            count = 0
            for combo in product(*block_lists):
                configs.append((list(combo), st))
                count += 1
                if count >= max_combos:
                    break
        else:
            for combo in product(*block_lists):
                configs.append((list(combo), st))

    return configs


# ============================================================================
# Main experiment
# ============================================================================

def run_experiment_for_n(N, selected_blocks, target_alphas, max_blocks=3, timeout=30):
    """Run SAT-optimal cross-edge search for all block configs at target N."""
    print(f"\n{'='*60}")
    print(f"N={N}")
    print(f"{'='*60}")

    sat_opt = load_sat_optimal(N)
    if sat_opt:
        print(f"  SAT-optimal benchmark: c={sat_opt['c']:.4f}, "
              f"α={sat_opt['alpha']}, d={sat_opt['d_max']}")

    configs = generate_configs(N, selected_blocks, max_blocks=max_blocks)
    print(f"  Configurations to test: {len(configs)}")
    print(f"  Target α values: {target_alphas}")

    results = []
    best_c = float("inf")
    best_result = None

    t0 = time.time()

    for cfg_idx, (block_infos, size_tuple) in enumerate(configs):
        for target_alpha in target_alphas:
            # Quick skip: all blocks must have alpha ≤ target
            if any(bi["alpha"] > target_alpha for bi in block_infos):
                continue

            result = find_best_for_blocks(block_infos, target_alpha, timeout=timeout)
            if result is None:
                continue

            result["block_ids"] = [bi["block_id"] for bi in block_infos]
            result["size_tuple"] = list(size_tuple)
            result["block_alphas"] = [bi["alpha"] for bi in block_infos]
            result["N"] = N
            results.append(result)

            if result["c"] is not None and result["c"] < best_c:
                best_c = result["c"]
                best_result = result

        if (cfg_idx + 1) % 50 == 0 or cfg_idx == len(configs) - 1:
            elapsed = time.time() - t0
            best_str = f"best c={best_c:.4f}" if best_c < float("inf") else "no feasible"
            print(f"    [{cfg_idx+1}/{len(configs)}] {elapsed:.1f}s, "
                  f"{len(results)} feasible, {best_str}")

    elapsed = time.time() - t0
    print(f"\n  Completed in {elapsed:.1f}s: {len(results)} feasible results")

    if best_result:
        sizes_str = "+".join(str(s) for s in best_result["size_tuple"])
        alphas_str = "+".join(str(a) for a in best_result["block_alphas"])
        print(f"  Best: c={best_result['c']:.4f}, α={best_result['actual_alpha']}, "
              f"d={best_result['d_max']}, blocks={sizes_str} "
              f"(α={alphas_str}), target_α={best_result['target_alpha']}")
        if sat_opt:
            gap = best_result["c"] - sat_opt["c"]
            print(f"  Gap to SAT-optimal: {gap:+.4f}")

    return results, best_result, sat_opt


def main():
    parser = argparse.ArgumentParser(description="Block optimal cross-edge experiment")
    parser.add_argument("--n-values", type=int, nargs="+", default=[10, 12, 14, 16],
                        help="Target N values")
    parser.add_argument("--max-per-size", type=int, default=20,
                        help="Max representative blocks per size (default: 20)")
    parser.add_argument("--max-blocks", type=int, default=3,
                        help="Max number of blocks per composition (default: 3)")
    parser.add_argument("--timeout", type=int, default=30,
                        help="SAT timeout per call in seconds (default: 30)")
    args = parser.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)

    # Load and select blocks
    print("Loading library...")
    library = load_library()
    print(f"  {len(library)} total blocks")

    selected_raw = select_blocks(library, max_per_group=3, max_per_size=args.max_per_size)
    for n in sorted(selected_raw.keys()):
        print(f"    n={n}: {len(selected_raw[n])} selected")

    # Precompute block info
    print("\nPrecomputing block structures...")
    selected = {}
    for n, blocks in selected_raw.items():
        selected[n] = [precompute_block(b) for b in blocks]
    print("  Done.")

    # Target alpha values per N
    default_targets = {
        10: [2, 3, 4],
        12: [3, 4],
        13: [3, 4],
        14: [3, 4, 5],
        15: [3, 4, 5],
        16: [3, 4, 5],
        17: [3, 4, 5],
        18: [3, 4, 5],
        19: [3, 4, 5],
        20: [3, 4, 5],
        21: [4, 5],
        22: [4, 5],
        23: [4, 5, 6],
        24: [4, 5, 6],
    }

    all_results = {}
    all_summaries = {}

    for N in args.n_values:
        targets = default_targets.get(N, [3, 4, 5])
        results, best, sat_opt = run_experiment_for_n(
            N, selected, targets,
            max_blocks=args.max_blocks, timeout=args.timeout
        )
        all_results[N] = results
        all_summaries[N] = {
            "num_feasible": len(results),
            "best": best,
            "sat_optimal": sat_opt,
        }

    # Save results
    results_path = os.path.join(OUTDIR, "results.json")
    with open(results_path, "w") as f:
        json.dump({str(k): v for k, v in all_results.items()}, f, indent=2)
    print(f"\nSaved {results_path}")

    # Save summary
    summary = {}
    for N in args.n_values:
        s = all_summaries.get(N, {})
        best = s.get("best")
        sat_opt = s.get("sat_optimal")
        entry = {
            "num_feasible": s.get("num_feasible", 0),
            "sat_optimal_c": sat_opt["c"] if sat_opt else None,
            "sat_optimal_alpha": sat_opt["alpha"] if sat_opt else None,
            "sat_optimal_d_max": sat_opt["d_max"] if sat_opt else None,
        }
        if best:
            entry.update({
                "best_c": best["c"],
                "best_alpha": best["actual_alpha"],
                "best_d_max": best["d_max"],
                "best_sizes": "+".join(str(s) for s in best["size_tuple"]),
                "best_target_alpha": best["target_alpha"],
                "best_degree_sequence": best["degree_sequence"],
                "best_g6": best["g6"],
                "gap_to_sat": round(best["c"] - sat_opt["c"], 4) if sat_opt and best["c"] else None,
            })
        summary[str(N)] = entry

    summary_path = os.path.join(OUTDIR, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved {summary_path}")

    # === Final summary table ===
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"\n  {'N':<4} {'Best c':<10} {'α':<4} {'d_max':<6} {'Blocks':<12} "
          f"{'SAT-opt c':<10} {'Gap':<8}")
    print(f"  {'-'*60}")

    for N in args.n_values:
        s = summary.get(str(N), {})
        if s.get("best_c") is None:
            sat_str = f"{s['sat_optimal_c']:.4f}" if s.get("sat_optimal_c") else "N/A"
            print(f"  {N:<4} {'N/A':<10} {'':4} {'':6} {'':12} {sat_str:<10}")
            continue

        gap_str = f"{s['gap_to_sat']:+.4f}" if s.get("gap_to_sat") is not None else "N/A"
        sat_str = f"{s['sat_optimal_c']:.4f}" if s.get("sat_optimal_c") else "N/A"
        sizes = s.get("best_sizes", "?")

        print(f"  {N:<4} {s['best_c']:<10.4f} {s['best_alpha']:<4} "
              f"{s['best_d_max']:<6} {sizes:<12} {sat_str:<10} {gap_str:<8}")

    print("\nDone.")


if __name__ == "__main__":
    main()
