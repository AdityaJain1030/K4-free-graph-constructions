#!/usr/bin/env python3
"""
Edge Trimming for Block Compositions
=====================================
Post-processes IS-join compositions by removing redundant edges
(edges whose removal doesn't increase α).  This produces α-critical
graphs with the same α but lower d_max, improving c values.

Also checks whether SAT-optimal graphs decompose as IS-joins.

Usage
-----
  # Default: load enriched round-1 results, trim, enrich, compare
  python run_trimming.py

  # Custom inputs
  python run_trimming.py --library ../library.json --compositions ../compositions.json

  # More trimming attempts
  python run_trimming.py --n-seeds 10

  # Skip slow steps
  python run_trimming.py --skip-enrichment --skip-decomposition
"""

import argparse
import json
import math
import os
import random
import sys
import time
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm

# Import core functions from parent module
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from run_experiment import (
    alpha_exact, alpha_sat, alpha_of_subset,
    is_k4_free, canonical_cert, compute_c_value,
    construct_composition_adj, find_alpha_dropping_sets,
    adj_to_graph6, graph6_to_adj,
    bitmask_to_list, list_to_bitmask,
    enumerate_compositions, sat_verify_top, score_composition,
    check_alpha_critical,
)

sys.stdout.reconfigure(line_buffering=True)

PARETO_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "..",
    "SAT_old", "pareto_reference",
))


# ============================================================================
# Core: Edge trimming
# ============================================================================

def trim_to_alpha_critical(adj, target_alpha, seed=42):
    """Remove redundant edges greedily until α-critical.

    An edge is redundant if removing it doesn't increase α.
    Result has α(G) = target_alpha and every edge is essential.
    Uses alpha_exact (bitmask B&B) for n ≤ 20, alpha_sat for larger.
    """
    adj = np.copy(adj)
    n = adj.shape[0]
    edges = [(i, j) for i in range(n) for j in range(i + 1, n) if adj[i, j]]
    rng = random.Random(seed)
    rng.shuffle(edges)
    edges_removed = 0
    use_exact = n <= 20

    for u, v in edges:
        if not adj[u, v]:
            continue
        adj[u, v] = adj[v, u] = False
        if use_exact:
            a, _ = alpha_exact(adj)
        else:
            a, _, _ = alpha_sat(adj, timeout=30)
        if a > target_alpha:
            adj[u, v] = adj[v, u] = True  # critical — restore
        else:
            edges_removed += 1

    d_max = int(adj.sum(axis=1).max()) if n > 0 else 0
    return adj, edges_removed, d_max


def trim_multi_seed(adj, target_alpha, n_seeds=5, base_seed=42):
    """Run trimming with multiple random seeds, return best (lowest c)."""
    n = adj.shape[0]
    best_adj = None
    best_c = float("inf")
    best_info = None
    all_results = []

    for s in range(n_seeds):
        seed = base_seed + s * 1000
        trimmed, removed, d_max = trim_to_alpha_critical(
            adj, target_alpha, seed=seed
        )
        c = compute_c_value(target_alpha, n, d_max)
        info = {
            "seed": seed,
            "edges_removed": removed,
            "d_max": d_max,
            "c_trimmed": round(c, 6) if c != float("inf") else None,
            "num_edges": int(trimmed.sum()) // 2,
            "degree_sequence": sorted(
                [int(trimmed[i].sum()) for i in range(n)], reverse=True
            ),
        }
        all_results.append(info)
        if c < best_c:
            best_c = c
            best_adj = trimmed
            best_info = info

    return best_adj, best_info, all_results


def verify_alpha_critical_full(adj, alpha):
    """Verify every remaining edge is critical (removing increases α)."""
    adj = np.copy(adj)
    n = adj.shape[0]
    use_exact = n <= 20
    for i in range(n):
        for j in range(i + 1, n):
            if not adj[i, j]:
                continue
            adj[i, j] = adj[j, i] = False
            if use_exact:
                a, _ = alpha_exact(adj)
            else:
                a, _, _ = alpha_sat(adj, timeout=30)
            adj[i, j] = adj[j, i] = True
            if a <= alpha:
                return False
    return True


# ============================================================================
# IS-join decomposition check
# ============================================================================

def check_is_join_decomposition(adj, max_decompositions=100):
    """Check if graph decomposes as an IS-join.

    Tries all non-trivial vertex partitions V = V_A ∪ V_B and checks
    whether cross-edges form a complete bipartite graph between
    independent connector sets I_A ⊆ V_A and I_B ⊆ V_B.

    Only feasible for n ≤ 18 (iterates 2^n subsets).
    Returns list of valid decomposition dicts.
    """
    n = adj.shape[0]
    if n > 18:
        return []

    all_verts = set(range(n))
    decompositions = []

    for mask in range(3, 1 << n):
        if len(decompositions) >= max_decompositions:
            break

        # Extract vertex sets from bitmask
        v_a = bitmask_to_list(mask, n)
        compl = ((1 << n) - 1) ^ mask
        v_b = bitmask_to_list(compl, n)

        if len(v_a) < 2 or len(v_b) < 2:
            continue
        # Symmetry: only check when min(v_a) < min(v_b)
        if v_a[0] > v_b[0]:
            continue

        v_a_set = set(v_a)
        v_b_set = set(v_b)

        # Find cross-edge endpoints
        i_a = set()
        i_b = set()
        for u in v_a:
            for v in v_b:
                if adj[u, v]:
                    i_a.add(u)
                    i_b.add(v)

        if not i_a or not i_b:
            continue

        # Check complete bipartite between I_A and I_B
        complete = True
        for u in i_a:
            for v in i_b:
                if not adj[u, v]:
                    complete = False
                    break
            if not complete:
                break
        if not complete:
            continue

        # Check I_A is independent in G[V_A]
        i_a_list = sorted(i_a)
        ok = True
        for x in range(len(i_a_list)):
            for y in range(x + 1, len(i_a_list)):
                if adj[i_a_list[x], i_a_list[y]]:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue

        # Check I_B is independent in G[V_B]
        i_b_list = sorted(i_b)
        ok = True
        for x in range(len(i_b_list)):
            for y in range(x + 1, len(i_b_list)):
                if adj[i_b_list[x], i_b_list[y]]:
                    ok = False
                    break
            if not ok:
                break
        if not ok:
            continue

        # Valid IS-join! Compute α of each block.
        sub_a = adj[np.ix_(v_a, v_a)]
        sub_b = adj[np.ix_(v_b, v_b)]
        alpha_a, _ = alpha_exact(sub_a)
        alpha_b, _ = alpha_exact(sub_b)

        decompositions.append({
            "v_a": v_a,
            "v_b": v_b,
            "i_a": i_a_list,
            "i_b": i_b_list,
            "size_a": len(v_a),
            "size_b": len(v_b),
            "alpha_a": alpha_a,
            "alpha_b": alpha_b,
            "alpha_join": alpha_a + alpha_b - 1,
            "connector_sizes": [len(i_a_list), len(i_b_list)],
        })

    return decompositions


# ============================================================================
# SAT-optimal data loading
# ============================================================================

def load_pareto_best_c(n_values):
    """Load best c values from SAT-optimal pareto data for each N."""
    result = {}
    for n in n_values:
        path = os.path.join(PARETO_DIR, f"pareto_n{n}.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            data = json.load(f)
        best_c = float("inf")
        best_entry = None
        for entry in data.get("pareto_frontier", []):
            c = entry.get("c_log")
            if c is not None and c < best_c:
                best_c = c
                best_entry = entry
        if best_entry:
            result[n] = {
                "c": round(best_c, 4),
                "alpha": best_entry["alpha"],
                "d_max": best_entry["d_max"],
                "g6": best_entry.get("g6"),
                "num_edges": len(best_entry.get("edges", [])),
            }
    return result


def load_pareto_graph(n, alpha=None, d_max=None):
    """Load a specific pareto-optimal graph as adjacency matrix."""
    path = os.path.join(PARETO_DIR, f"pareto_n{n}.json")
    if not os.path.isfile(path):
        return None, None
    with open(path) as f:
        data = json.load(f)
    for entry in data.get("pareto_frontier", []):
        if alpha is not None and entry["alpha"] != alpha:
            continue
        if d_max is not None and entry["d_max"] != d_max:
            continue
        adj = np.zeros((n, n), dtype=np.bool_)
        for u, v in entry["edges"]:
            adj[u, v] = adj[v, u] = True
        return adj, entry
    return None, None


def load_all_pareto_n16():
    """Load all pareto frontier entries at N=16."""
    path = os.path.join(PARETO_DIR, "pareto_n16.json")
    if not os.path.isfile(path):
        return []
    with open(path) as f:
        data = json.load(f)
    entries = []
    for entry in data.get("pareto_frontier", []):
        adj = np.zeros((16, 16), dtype=np.bool_)
        for u, v in entry["edges"]:
            adj[u, v] = adj[v, u] = True
        entries.append((adj, entry))
    return entries


# ============================================================================
# Main pipeline
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Edge trimming for block compositions"
    )
    parser.add_argument("--library", default=None,
                        help="Path to library.json")
    parser.add_argument("--compositions", default=None,
                        help="Path to compositions.json (round 1 recommended)")
    parser.add_argument("--n-seeds", type=int, default=5,
                        help="Trimming seeds per graph (default: 5)")
    parser.add_argument("--sat-timeout", type=int, default=120,
                        help="SAT timeout per call in seconds (default: 120)")
    parser.add_argument("--outdir", default=None,
                        help="Output directory (default: trimming/)")
    parser.add_argument("--skip-enrichment", action="store_true",
                        help="Skip enrichment with trimmed blocks")
    parser.add_argument("--skip-decomposition", action="store_true",
                        help="Skip IS-join decomposition check")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    outdir = args.outdir or os.path.dirname(os.path.abspath(__file__))
    os.makedirs(outdir, exist_ok=True)
    os.makedirs(os.path.join(outdir, "plots"), exist_ok=True)

    lib_path = args.library or os.path.join(
        base_dir, "library_enriched_round1.json"
    )
    comp_path = args.compositions or os.path.join(
        base_dir, "compositions_round1.json"
    )

    print(f"Loading library from {lib_path}")
    with open(lib_path) as f:
        library = json.load(f)
    print(f"  {len(library)} blocks")

    print(f"Loading compositions from {comp_path}")
    with open(comp_path) as f:
        compositions = json.load(f)
    print(f"  {len(compositions)} compositions")

    block_map = {b["block_id"]: b for b in library}
    t_start = time.time()

    # ── Step 1: Select compositions with balanced N coverage ────
    print("\n" + "=" * 60)
    print("STEP 1: Select compositions across all N values")
    print("=" * 60)

    by_n = defaultdict(list)
    for comp in compositions:
        by_n[comp["n_total"]].append(comp)
    for n_key in by_n:
        by_n[n_key].sort(
            key=lambda x: x.get("c_arithmetic", float("inf"))
        )

    n_values = sorted(by_n.keys())
    per_n = {}
    remaining = 50
    for n_val in n_values:
        k = min(remaining, min(15, len(by_n[n_val])))
        per_n[n_val] = k
        remaining -= k
    # Give leftover slots to largest N values
    for n_val in reversed(n_values):
        if remaining <= 0:
            break
        extra = min(remaining, len(by_n[n_val]) - per_n.get(n_val, 0))
        if extra > 0:
            per_n[n_val] = per_n.get(n_val, 0) + extra
            remaining -= extra

    selected = []
    for n_val in sorted(per_n.keys()):
        k = per_n[n_val]
        selected.extend(by_n[n_val][:k])
        best_c = by_n[n_val][0]["c_arithmetic"]
        print(f"  N={n_val}: selecting {k} compositions "
              f"(best c = {best_c:.4f})")
    print(f"  Total selected: {len(selected)}")

    # ── SAT-verify selected compositions ────────────────────────
    print("\n  SAT-verifying selected compositions...")
    verified = []
    for comp in tqdm(selected, desc="  SAT verify"):
        bid_a = comp["block_A_id"]
        bid_b = comp["block_B_id"]
        if bid_a not in block_map or bid_b not in block_map:
            continue
        block_a = block_map[bid_a]
        block_b = block_map[bid_b]
        da = {"vertices": comp["drop_set_A"],
              "size": len(comp["drop_set_A"])}
        db = {"vertices": comp["drop_set_B"],
              "size": len(comp["drop_set_B"])}

        adj = construct_composition_adj(block_a, block_b, da, db)
        n = adj.shape[0]

        if not is_k4_free(adj):
            continue

        if n <= 20:
            alpha_true, _ = alpha_exact(adj)
            timed_out = False
        else:
            alpha_true, _, timed_out = alpha_sat(adj, timeout=args.sat_timeout)

        if timed_out:
            continue

        d_max_orig = int(adj.sum(axis=1).max())
        c_orig = compute_c_value(alpha_true, n, d_max_orig)

        verified.append({
            "comp": comp,
            "adj": adj,
            "n": n,
            "alpha": alpha_true,
            "d_max_original": d_max_orig,
            "c_original": round(c_orig, 6),
            "num_edges_original": int(adj.sum()) // 2,
        })

    print(f"  Verified: {len(verified)}")

    # ── Step 2: Trim each composition ───────────────────────────
    print("\n" + "=" * 60)
    print(f"STEP 2: Trimming ({args.n_seeds} seeds each)")
    print("=" * 60)

    trimming_results = []
    trimmed_adjs = []

    for entry in tqdm(verified, desc="  Trimming"):
        adj = entry["adj"]
        alpha = entry["alpha"]
        n = entry["n"]

        best_adj, best_info, all_seeds = trim_multi_seed(
            adj, alpha, n_seeds=args.n_seeds
        )

        # Verify α-critical on the best trimmed graph
        is_critical = verify_alpha_critical_full(best_adj, alpha)

        result = {
            "n": n,
            "alpha": alpha,
            "c_original": entry["c_original"],
            "d_max_original": entry["d_max_original"],
            "num_edges_original": entry["num_edges_original"],
            "c_trimmed": best_info["c_trimmed"],
            "d_max_trimmed": best_info["d_max"],
            "num_edges_trimmed": best_info["num_edges"],
            "edges_removed": best_info["edges_removed"],
            "degree_sequence_trimmed": best_info["degree_sequence"],
            "is_alpha_critical": is_critical,
            "best_seed": best_info["seed"],
            "g6_trimmed": adj_to_graph6(best_adj),
            "block_A_id": entry["comp"]["block_A_id"],
            "block_B_id": entry["comp"]["block_B_id"],
            "all_seeds": all_seeds,
        }
        trimming_results.append(result)
        trimmed_adjs.append(best_adj)

    # Print summary by N
    print("\n  Trimming summary by N:")
    by_n_results = defaultdict(list)
    for r in trimming_results:
        by_n_results[r["n"]].append(r)

    for n_val in sorted(by_n_results.keys()):
        results_n = by_n_results[n_val]
        c_orig = [r["c_original"] for r in results_n]
        c_trim = [r["c_trimmed"] for r in results_n if r["c_trimmed"]]
        edges_rm = [r["edges_removed"] for r in results_n]
        all_critical = all(r["is_alpha_critical"] for r in results_n)
        print(f"    N={n_val:3d}: {len(results_n)} graphs")
        print(f"      c original: best={min(c_orig):.4f}  "
              f"mean={sum(c_orig)/len(c_orig):.4f}")
        if c_trim:
            print(f"      c trimmed:  best={min(c_trim):.4f}  "
                  f"mean={sum(c_trim)/len(c_trim):.4f}")
            print(f"      improvement: {min(c_orig) - min(c_trim):+.4f} (best)")
        print(f"      edges removed: {min(edges_rm)}-{max(edges_rm)}")
        print(f"      all alpha-critical: {all_critical}")
        if c_trim:
            best_r = min(results_n, key=lambda r: r["c_trimmed"] or 99)
            print(f"      best trimmed degree seq: "
                  f"{best_r['degree_sequence_trimmed']}")

    trim_path = os.path.join(outdir, "trimming_results.json")
    with open(trim_path, "w") as f:
        json.dump(trimming_results, f, indent=2)
    print(f"\n  Saved to {trim_path}")

    # ── Step 3: Find α-dropping sets for trimmed graphs ─────────
    print("\n" + "=" * 60)
    print("STEP 3: Finding alpha-dropping sets for trimmed graphs")
    print("=" * 60)

    trimmed_blocks = []
    next_block_id = max(b["block_id"] for b in library) + 1
    seen_certs = set()

    for i, (result, adj) in enumerate(tqdm(
        zip(trimming_results, trimmed_adjs),
        desc="  Finding drops", total=len(trimmed_adjs)
    )):
        n = result["n"]
        alpha = result["alpha"]

        cert = canonical_cert(adj)
        if cert in seen_certs:
            continue
        seen_certs.add(cert)

        cap = 10000 if n <= 16 else 5000
        dropping = find_alpha_dropping_sets(adj, alpha, max_is=cap)
        if not dropping:
            continue

        degrees = [int(adj[v].sum()) for v in range(n)]
        d_max = max(degrees)

        block = {
            "block_id": next_block_id,
            "n": n,
            "g6": result["g6_trimmed"],
            "edges": [[int(u), int(v)] for u in range(n)
                      for v in range(u + 1, n) if adj[u, v]],
            "num_edges": result["num_edges_trimmed"],
            "alpha": alpha,
            "is_alpha_critical": result["is_alpha_critical"],
            "alpha_dropping_sets": dropping,
            "degree_sequence": sorted(degrees, reverse=True),
            "d_max": d_max,
            "source": "trimmed_composition",
        }
        trimmed_blocks.append(block)
        next_block_id += 1

    print(f"\n  Trimmed blocks with alpha-dropping sets: "
          f"{len(trimmed_blocks)}")
    for b in trimmed_blocks:
        c_val = compute_c_value(b["alpha"], b["n"], b["d_max"])
        print(f"    n={b['n']}, alpha={b['alpha']}, d_max={b['d_max']}, "
              f"c={c_val:.4f}, drops={len(b['alpha_dropping_sets'])}")

    blocks_path = os.path.join(outdir, "trimmed_blocks.json")
    with open(blocks_path, "w") as f:
        json.dump(trimmed_blocks, f, indent=2)
    print(f"  Saved to {blocks_path}")

    # ── Step 4: Enrichment with trimmed blocks ──────────────────
    enrichment_results = None
    if not trimmed_blocks:
        print("\n  Note: 0 trimmed blocks have alpha-dropping sets.")
        print("  This is expected: alpha-critical graphs and alpha-dropping")
        print("  sets are incompatible. Trimmed blocks cannot be composed")
        print("  via IS-join. Skipping enrichment.")
        enrichment_results = {
            "skipped": True,
            "reason": "alpha-critical graphs have no alpha-dropping sets",
            "trimmed_blocks_checked": len(trimming_results),
            "trimmed_blocks_with_drops": 0,
        }
    if not args.skip_enrichment and trimmed_blocks:
        print("\n" + "=" * 60)
        print("STEP 4: Enrichment with trimmed blocks")
        print("=" * 60)

        enriched_library = library + trimmed_blocks
        print(f"  Enriched library: {len(enriched_library)} blocks "
              f"(+{len(trimmed_blocks)} trimmed)")

        new_comps, new_valid = enumerate_compositions(
            enriched_library, top_k=10000
        )

        # SAT-verify top 50
        new_sat = []
        if new_comps:
            new_sat = sat_verify_top(new_comps, enriched_library, k=50)

        # Collect results
        best_by_n = defaultdict(lambda: float("inf"))
        for comp in new_comps:
            n = comp["n_total"]
            c = comp.get("c_arithmetic")
            if c is not None:
                best_by_n[n] = min(best_by_n[n], c)

        enrichment_results = {
            "enriched_library_size": len(enriched_library),
            "trimmed_blocks_added": len(trimmed_blocks),
            "total_compositions": new_valid,
            "stored_compositions": len(new_comps),
            "sat_verified": len([r for r in new_sat
                                 if r.get("alpha_sat") is not None]),
            "alpha_matches": len([r for r in new_sat
                                  if r.get("alpha_match")]),
            "best_c_by_n": {
                str(n): round(best_by_n[n], 4)
                for n in sorted(best_by_n.keys())
            },
        }

        enrich_path = os.path.join(outdir, "enrichment_with_trimming.json")
        with open(enrich_path, "w") as f:
            json.dump(enrichment_results, f, indent=2)

        print(f"\n  Best c by N (with trimmed blocks):")
        for n in sorted(best_by_n.keys()):
            print(f"    N={n:3d}: c = {best_by_n[n]:.4f}")
        print(f"  Saved to {enrich_path}")

    # ── Step 5: SAT-optimal comparison ──────────────────────────
    print("\n" + "=" * 60)
    print("STEP 5: Comparison with SAT-optimal")
    print("=" * 60)

    n_vals_present = sorted(set(r["n"] for r in trimming_results))
    pareto_best = load_pareto_best_c(
        list(set(n_vals_present + list(range(10, 23))))
    )

    comparison = []
    for n_val in sorted(set(n_vals_present)):
        results_n = [r for r in trimming_results if r["n"] == n_val]
        best_orig = min(r["c_original"] for r in results_n)
        c_trim_vals = [r["c_trimmed"] for r in results_n if r["c_trimmed"]]
        best_trim = min(c_trim_vals) if c_trim_vals else None
        sat_opt = pareto_best.get(n_val)

        row = {
            "n": n_val,
            "c_original": round(best_orig, 4),
            "c_trimmed": round(best_trim, 4) if best_trim else None,
            "c_sat_optimal": sat_opt["c"] if sat_opt else None,
            "alpha_sat_optimal": sat_opt["alpha"] if sat_opt else None,
            "d_max_sat_optimal": sat_opt["d_max"] if sat_opt else None,
        }
        if best_trim is not None and sat_opt:
            row["gap_to_optimal"] = round(best_trim - sat_opt["c"], 4)
            row["improvement_pct"] = round(
                (best_orig - best_trim) / best_orig * 100, 1
            )
        comparison.append(row)

        sat_str = (f"SAT-opt={sat_opt['c']:.4f}"
                   if sat_opt else "no SAT data")
        trim_str = (f"trimmed={best_trim:.4f}"
                    if best_trim else "n/a")
        print(f"  N={n_val:3d}: original={best_orig:.4f}  "
              f"{trim_str}  {sat_str}")
        if best_trim is not None and sat_opt:
            gap = best_trim - sat_opt["c"]
            pct = (best_orig - best_trim) / best_orig * 100
            print(f"         gap to optimal: {gap:+.4f}  "
                  f"improvement: {pct:.1f}%")

    comp_table_path = os.path.join(outdir, "comparison_table.json")
    with open(comp_table_path, "w") as f:
        json.dump(comparison, f, indent=2)
    print(f"  Saved to {comp_table_path}")

    # ── Step 6: IS-join decomposition of SAT-optimal N=16 ───────
    decomp_results = {}
    if not args.skip_decomposition:
        print("\n" + "=" * 60)
        print("STEP 6: IS-join decomposition of SAT-optimal N=16")
        print("=" * 60)

        adj_opt, entry_opt = load_pareto_graph(16, alpha=4, d_max=4)
        if adj_opt is not None:
            print(f"  Graph: n=16, alpha={entry_opt['alpha']}, "
                  f"d_max={entry_opt['d_max']}, "
                  f"c={entry_opt['c_log']:.4f}")
            print(f"  g6: {entry_opt.get('g6', 'n/a')}")

            # Check isomorphism with trimmed compositions
            cert_opt = canonical_cert(adj_opt)
            iso_found = False
            for r in trimming_results:
                if r["n"] != 16:
                    continue
                adj_trim = graph6_to_adj(r["g6_trimmed"])
                if canonical_cert(adj_trim) == cert_opt:
                    iso_found = True
                    print("  *** ISOMORPHIC to trimmed composition! ***")
                    break
            if not iso_found:
                print("  Not isomorphic to any trimmed composition")

            # Check IS-join decomposition
            print("  Checking IS-join decomposition (2^16 partitions)...")
            t0 = time.time()
            decomps = check_is_join_decomposition(adj_opt)
            dt = time.time() - t0
            print(f"  Checked in {dt:.1f}s")

            if decomps:
                print(f"  *** FOUND {len(decomps)} IS-join "
                      f"decomposition(s)! ***")
                for d in decomps[:10]:
                    print(f"    |V_A|={d['size_a']}, |V_B|={d['size_b']}"
                          f", |I_A|={d['connector_sizes'][0]}"
                          f", |I_B|={d['connector_sizes'][1]}"
                          f", alpha_A={d['alpha_a']}"
                          f", alpha_B={d['alpha_b']}"
                          f", alpha_join={d['alpha_join']}")
            else:
                print("  No IS-join decomposition found "
                      "-- graph is NOT compositional")

            decomp_results["n16_alpha4_d4"] = {
                "g6": entry_opt.get("g6"),
                "isomorphic_to_trimmed": iso_found,
                "decompositions_found": len(decomps),
                "decompositions": decomps[:20],
            }

            # Check all N=16 pareto entries
            all_n16 = load_all_pareto_n16()
            if all_n16:
                print(f"\n  All N=16 pareto frontier entries:")
                for idx, (adj_p, entry_p) in enumerate(all_n16):
                    d_p = check_is_join_decomposition(adj_p, 5)
                    c_str = (f"c={entry_p['c_log']:.4f}"
                             if entry_p.get("c_log") else "c=n/a")
                    tag = "YES" if d_p else "NO"
                    print(f"    [{idx}] alpha={entry_p['alpha']}, "
                          f"d_max={entry_p['d_max']}, {c_str}: "
                          f"{tag} ({len(d_p)} decomp)")
                    decomp_results[f"n16_entry_{idx}"] = {
                        "alpha": entry_p["alpha"],
                        "d_max": entry_p["d_max"],
                        "c": entry_p.get("c_log"),
                        "decomposes": len(d_p) > 0,
                        "num_decompositions": len(d_p),
                    }
        else:
            print("  N=16 pareto data not found")

        decomp_path = os.path.join(outdir, "decomposition_check.json")
        with open(decomp_path, "w") as f:
            json.dump(decomp_results, f, indent=2, default=str)
        print(f"  Saved to {decomp_path}")

    # ── Plots ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Generating plots")
    print("=" * 60)

    plots_dir = os.path.join(outdir, "plots")

    # ── Plot 1: c before/after trimming (grouped bar) ───────────
    fig, ax = plt.subplots(figsize=(10, 6))
    n_vals = sorted(set(r["n"] for r in trimming_results))
    x = np.arange(len(n_vals))
    width = 0.25

    c_orig_best = []
    c_trim_best = []
    c_sat_vals = []
    for n_val in n_vals:
        rn = [r for r in trimming_results if r["n"] == n_val]
        c_orig_best.append(min(r["c_original"] for r in rn))
        ct = [r["c_trimmed"] for r in rn if r["c_trimmed"]]
        c_trim_best.append(min(ct) if ct else 0)
        c_sat_vals.append(
            pareto_best[n_val]["c"] if n_val in pareto_best else 0
        )

    bars1 = ax.bar(x - width, c_orig_best, width,
                   label="Original (IS-join)", color="#4472C4")
    bars2 = ax.bar(x, c_trim_best, width,
                   label="Trimmed (alpha-critical)", color="#ED7D31")
    bars3 = ax.bar(x + width, c_sat_vals, width,
                   label="SAT-optimal", color="#70AD47")

    ax.set_xlabel("N (total vertices)")
    ax.set_ylabel("Best c = alpha * d_max / (N * ln(d_max))")
    ax.set_title("c-value: Original vs Trimmed vs SAT-Optimal")
    ax.set_xticks(x)
    ax.set_xticklabels([str(n) for n in n_vals])
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.annotate(
                    f"{h:.3f}",
                    xy=(bar.get_x() + bar.get_width() / 2, h),
                    xytext=(0, 3), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8,
                )

    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "c_before_after_trim.png"), dpi=150)
    plt.close()

    # ── Plot 2: c vs N comprehensive ────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 7))

    # All trimming results as scatter
    for r in trimming_results:
        if r["c_trimmed"]:
            ax.scatter(r["n"], r["c_trimmed"], color="#ED7D31",
                       alpha=0.3, s=20, zorder=2)

    # Best trimmed per N
    ax.plot(n_vals, c_trim_best, "o-", color="#ED7D31", markersize=8,
            linewidth=2, label="Block composition (trimmed)", zorder=3)

    # Original per N
    ax.plot(n_vals, c_orig_best, "s--", color="#4472C4", markersize=8,
            linewidth=2, label="Block composition (original)", zorder=3)

    # SAT-optimal curve
    sat_ns = sorted(pareto_best.keys())
    sat_cs = [pareto_best[n]["c"] for n in sat_ns]
    ax.plot(sat_ns, sat_cs, "D-", color="#70AD47", markersize=6,
            linewidth=2, label="SAT-optimal (pareto)", zorder=4)

    # Enrichment results if available
    if enrichment_results and "best_c_by_n" in enrichment_results:
        en_ns = sorted(int(k)
                       for k in enrichment_results["best_c_by_n"].keys())
        en_cs = [enrichment_results["best_c_by_n"][str(n)] for n in en_ns]
        ax.plot(en_ns, en_cs, "^:", color="#FF0000", markersize=8,
                linewidth=2, label="Enriched with trimmed blocks",
                zorder=4)

    ax.set_xlabel("N (total vertices)")
    ax.set_ylabel("c = alpha * d_max / (N * ln(d_max))")
    ax.set_title("Best c-value by N: Block Composition Pipeline")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0.5)
    plt.tight_layout()
    plt.savefig(
        os.path.join(plots_dir, "c_vs_n_with_trimming.png"), dpi=150
    )
    plt.close()

    print(f"  Plots saved to {plots_dir}/")

    # ── Final summary ───────────────────────────────────────────
    wall_time = round(time.time() - t_start, 1)

    summary = {
        "wall_time_s": wall_time,
        "compositions_selected": len(selected),
        "compositions_verified": len(verified),
        "compositions_trimmed": len(trimming_results),
        "trimmed_blocks_with_drops": len(trimmed_blocks),
        "comparison": comparison,
        "enrichment": enrichment_results,
        "decomposition": decomp_results if decomp_results else None,
    }
    summary_path = os.path.join(outdir, "trimming_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n  Summary saved to {summary_path}")
    print(f"\n  Total wall time: {wall_time:.1f}s")
    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
