#!/usr/bin/env python3
"""
Block Decomposition Experiment for K₄-Free Graphs
===================================================
Tests whether good K₄-free graphs (low c = α·d_max/(N·ln d_max))
can be built by composing smaller blocks via IS-join — a graph
composition that preserves K₄-freeness and allows arithmetic α
computation.

Phase 1: Build a library of small K₄-free blocks with α-dropping sets
Phase 2: Enumerate all depth-1 IS-join compositions, SAT-verify top 50
Phase 3: Analyze results, compare to Experiment 1 baselines

Usage
-----
  # Default (n <= 8, fast)
  python run_experiment.py

  # Extend to n=9 (slower library build, many more blocks)
  python run_experiment.py --max-n 9

  # Include SAT-optimal graphs from pareto data as extra blocks
  python run_experiment.py --include-pareto

  # Quick test
  python run_experiment.py --max-n 6
"""

import argparse
import heapq
import json
import math
import os
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx
import pynauty
from tqdm import tqdm

from pysat.card import CardEnc, EncType
from pysat.solvers import Glucose4

sys.stdout.reconfigure(line_buffering=True)

PARETO_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "reference", "pareto"
)


# ============================================================================
# Core: exact independence number (bitmask branch-and-bound)
# ============================================================================

def alpha_exact(adj):
    """Exact independence number via bitmask branch-and-bound.
    Fast for n <= ~20. Returns (alpha_value, best_is_bitmask)."""
    n = adj.shape[0]
    if n == 0:
        return 0, 0

    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    best = [0]
    best_set = [0]

    def branch(cands, cur, size):
        if size + bin(cands).count("1") <= best[0]:
            return
        if cands == 0:
            if size > best[0]:
                best[0] = size
                best_set[0] = cur
            return
        v = (cands & -cands).bit_length() - 1
        branch(cands & ~nbr[v] & ~(1 << v), cur | (1 << v), size + 1)
        branch(cands & ~(1 << v), cur, size)

    branch((1 << n) - 1, 0, 0)
    return best[0], best_set[0]


def alpha_of_subset(adj, vertex_mask):
    """Compute alpha of the induced subgraph on vertices in vertex_mask."""
    n = adj.shape[0]
    verts = bitmask_to_list(vertex_mask, n)
    if not verts:
        return 0
    sub = adj[np.ix_(verts, verts)]
    a, _ = alpha_exact(sub)
    return a


# ============================================================================
# Core: SAT-based alpha (for larger composed graphs)
# ============================================================================

def alpha_sat(adj, timeout=60):
    """Exact alpha via SAT binary search. Returns (alpha, time_s, timed_out)."""
    n = adj.shape[0]
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                edges.append((i, j))

    t0 = time.time()
    lo, hi = 1, n
    best_alpha = 0
    total_timed_out = False

    while lo <= hi:
        mid = (lo + hi) // 2
        sat, to = _sat_check_is(n, edges, mid, timeout)
        if to:
            total_timed_out = True
            hi = mid - 1
            continue
        if sat:
            best_alpha = mid
            lo = mid + 1
        else:
            hi = mid - 1

    return best_alpha, time.time() - t0, total_timed_out


def _sat_check_is(n, edges, k, timeout):
    """Check if graph has IS of size >= k. Returns (sat, timed_out)."""
    solver = Glucose4()
    try:
        for i, j in edges:
            solver.add_clause([-(i + 1), -(j + 1)])
        lits = list(range(1, n + 1))
        cnf = CardEnc.atleast(lits, bound=k, top_id=n, encoding=EncType.totalizer)
        for cl in cnf.clauses:
            solver.add_clause(cl)
        flag = [False]

        def on_timeout():
            flag[0] = True
            solver.interrupt()

        timer = threading.Timer(timeout, on_timeout)
        timer.start()
        result = solver.solve_limited()
        timer.cancel()
        if flag[0] or result is None:
            return False, True
        return bool(result), False
    finally:
        solver.delete()


# ============================================================================
# K4-freeness check
# ============================================================================

def is_k4_free(adj):
    """Fast K4-free check using bitmask neighbor sets."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    for a in range(n):
        for b in range(a + 1, n):
            if not adj[a, b]:
                continue
            common = nbr[a] & nbr[b]
            while common:
                c = (common & -common).bit_length() - 1
                if nbr[c] & (common & ~(1 << c)):
                    return False
                common &= common - 1
    return True


# ============================================================================
# Bitmask / graph utilities
# ============================================================================

def bitmask_to_list(mask, n):
    """Convert bitmask to sorted list of vertex indices."""
    result = []
    m = mask
    while m:
        v = (m & -m).bit_length() - 1
        result.append(v)
        m &= m - 1
    return result


def list_to_bitmask(verts):
    mask = 0
    for v in verts:
        mask |= 1 << v
    return mask


def graph6_to_adj(g6):
    """Convert graph6 string to numpy bool adjacency matrix."""
    G = nx.from_graph6_bytes(g6.encode())
    n = G.number_of_nodes()
    adj = np.zeros((n, n), dtype=np.bool_)
    for u, v in G.edges():
        adj[u, v] = adj[v, u] = True
    return adj


def adj_to_graph6(adj):
    """Convert adjacency matrix to graph6 string."""
    n = adj.shape[0]
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                G.add_edge(i, j)
    return nx.to_graph6_bytes(G, header=False).decode().strip()


def canonical_cert(adj):
    """Canonical certificate via pynauty for deduplication."""
    n = adj.shape[0]
    g = pynauty.Graph(n)
    for i in range(n):
        nbrs = [int(j) for j in range(n) if j != i and adj[i, j]]
        if nbrs:
            g.connect_vertex(i, nbrs)
    return pynauty.certificate(g)


def compute_c_value(alpha, n, d_max):
    if d_max <= 1:
        return float("inf")
    return alpha * d_max / (n * math.log(d_max))


# ============================================================================
# Independent set enumeration (backtracking)
# ============================================================================

def enumerate_independent_sets(adj, max_count=50000):
    """Enumerate all non-empty independent sets via backtracking.
    Returns list of bitmasks. Caps at max_count to avoid blowup."""
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        for j in range(n):
            if adj[i, j]:
                nbr[i] |= 1 << j

    results = []
    capped = [False]

    def backtrack(v, cur, forbidden):
        if len(results) >= max_count:
            capped[0] = True
            return
        if cur:
            results.append(cur)
        for u in range(v, n):
            if not (forbidden & (1 << u)):
                backtrack(u + 1, cur | (1 << u), forbidden | nbr[u])

    backtrack(0, 0, 0)
    return results, capped[0]


# ============================================================================
# Phase 1: Build block library
# ============================================================================

def find_geng():
    """Locate the geng binary."""
    g = shutil.which("geng")
    if g:
        return g
    prefix = os.environ.get("CONDA_PREFIX", "")
    if prefix:
        p = os.path.join(prefix, "src", "nauty2_9_3", "geng")
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return None


def generate_k4free_for_n(n, geng_path, use_triangle_free=False):
    """Generate connected K4-free graphs on n vertices using geng.
    Returns list of graph6 strings."""
    cmd = [geng_path, str(n), "-c", "-q"]
    if use_triangle_free:
        cmd.append("-t")
    else:
        cmd.append("-k")

    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=600
    )
    lines = result.stdout.strip().split("\n")
    return [l.strip() for l in lines if l.strip() and not l.startswith(">>")]


def check_alpha_critical(adj, alpha):
    """Check if graph is alpha-critical: removing any edge increases alpha.
    Returns True if alpha-critical."""
    n = adj.shape[0]
    for i in range(n):
        for j in range(i + 1, n):
            if not adj[i, j]:
                continue
            # Remove edge (i, j)
            adj[i, j] = adj[j, i] = False
            a, _ = alpha_exact(adj)
            adj[i, j] = adj[j, i] = True
            if a <= alpha:
                return False
    return True


def find_alpha_dropping_sets(adj, alpha, max_is=50000):
    """Find all alpha-dropping independent sets.
    An IS I is alpha-dropping if alpha(G[V\\I]) = alpha - 1.
    Returns list of dicts with 'vertices', 'size', 'maximality_verified'."""
    n = adj.shape[0]
    all_verts_mask = (1 << n) - 1

    all_is, capped = enumerate_independent_sets(adj, max_count=max_is)

    dropping = []
    for is_mask in all_is:
        complement_mask = all_verts_mask & ~is_mask
        a_comp = alpha_of_subset(adj, complement_mask)
        if a_comp == alpha - 1:
            # Check maximality: each vertex in I is necessary
            verts_in_i = bitmask_to_list(is_mask, n)
            maximal = True
            for v in verts_in_i:
                # Add v back to complement
                aug_mask = complement_mask | (1 << v)
                a_aug = alpha_of_subset(adj, aug_mask)
                if a_aug != alpha:
                    maximal = False
                    break

            dropping.append({
                "vertices": verts_in_i,
                "size": len(verts_in_i),
                "maximality_verified": maximal,
            })

    return dropping


def load_pareto_blocks(max_n=15):
    """Load SAT-optimal graphs from pareto data as additional blocks."""
    blocks = []
    pareto_dir = os.path.normpath(PARETO_DIR)
    if not os.path.isdir(pareto_dir):
        print(f"  Pareto directory not found: {pareto_dir}")
        return blocks

    for fname in sorted(os.listdir(pareto_dir)):
        if not fname.startswith("pareto_n") or not fname.endswith(".json"):
            continue
        n_str = fname.replace("pareto_n", "").replace(".json", "")
        try:
            n = int(n_str)
        except ValueError:
            continue
        if n > max_n:
            continue

        path = os.path.join(pareto_dir, fname)
        with open(path) as f:
            data = json.load(f)

        for entry in data.get("pareto_frontier", []):
            adj = np.zeros((n, n), dtype=np.bool_)
            for u, v in entry["edges"]:
                adj[u, v] = adj[v, u] = True
            blocks.append({
                "adj": adj,
                "n": n,
                "alpha": entry["alpha"],
                "source": f"pareto_{fname}",
            })

    return blocks


def build_library(max_n, geng_path, include_pareto=False, pareto_max_n=15):
    """Build the complete block library."""
    print("=" * 60)
    print("PHASE 1: Building Block Library")
    print("=" * 60)

    seen_certs = set()
    library = []
    block_id = 0

    # Generate K4-free graphs for each n
    for n in range(3, max_n + 1):
        use_tf = (n >= 10)
        mode = "triangle-free" if use_tf else "K4-free"
        print(f"\n  n={n}: generating connected {mode} graphs...", end=" ", flush=True)
        g6_list = generate_k4free_for_n(n, geng_path, use_triangle_free=use_tf)
        print(f"{len(g6_list)} graphs")

        added = 0
        for g6 in tqdm(g6_list, desc=f"  n={n} processing", leave=False):
            adj = graph6_to_adj(g6)

            # Deduplicate
            cert = canonical_cert(adj)
            if cert in seen_certs:
                continue
            seen_certs.add(cert)

            # Compute alpha
            alpha, _ = alpha_exact(adj)
            if alpha <= 0:
                continue

            # Find alpha-dropping sets
            dropping = find_alpha_dropping_sets(adj, alpha)
            if not dropping:
                continue

            # Check alpha-critical
            is_critical = check_alpha_critical(adj, alpha)

            degrees = [int(adj[i].sum()) for i in range(n)]
            d_max = max(degrees)

            library.append({
                "block_id": block_id,
                "n": n,
                "g6": g6,
                "edges": [[int(i), int(j)] for i in range(n)
                          for j in range(i + 1, n) if adj[i, j]],
                "num_edges": int(adj.sum()) // 2,
                "alpha": alpha,
                "is_alpha_critical": is_critical,
                "alpha_dropping_sets": dropping,
                "degree_sequence": sorted(degrees, reverse=True),
                "d_max": d_max,
                "source": "geng",
            })
            block_id += 1
            added += 1

        print(f"  n={n}: {added} blocks with alpha-dropping sets")

    # Optionally load pareto blocks
    if include_pareto:
        print(f"\n  Loading pareto blocks (n <= {pareto_max_n})...")
        pareto_blocks = load_pareto_blocks(max_n=pareto_max_n)
        added = 0
        for pb in tqdm(pareto_blocks, desc="  Pareto blocks", leave=False):
            adj = pb["adj"]
            n = pb["n"]
            cert = canonical_cert(adj)
            if cert in seen_certs:
                continue
            seen_certs.add(cert)

            alpha = pb["alpha"]
            dropping = find_alpha_dropping_sets(adj, alpha, max_is=10000)
            if not dropping:
                continue

            is_critical = check_alpha_critical(adj, alpha)
            degrees = [int(adj[i].sum()) for i in range(n)]
            d_max = max(degrees)

            library.append({
                "block_id": block_id,
                "n": n,
                "g6": adj_to_graph6(adj),
                "edges": [[int(i), int(j)] for i in range(n)
                          for j in range(i + 1, n) if adj[i, j]],
                "num_edges": int(adj.sum()) // 2,
                "alpha": alpha,
                "is_alpha_critical": is_critical,
                "alpha_dropping_sets": dropping,
                "degree_sequence": sorted(degrees, reverse=True),
                "d_max": d_max,
                "source": pb["source"],
            })
            block_id += 1
            added += 1
        print(f"  Pareto: {added} new blocks added")

    print(f"\n  Library total: {len(library)} blocks")
    return library


# ============================================================================
# Phase 2: Exhaustive composition
# ============================================================================

def score_composition(block_a, block_b, drop_a, drop_b):
    """Compute IS-join score without building the graph.
    Returns dict with arithmetic c-value and degree info."""
    n_a, n_b = block_a["n"], block_b["n"]
    alpha_a, alpha_b = block_a["alpha"], block_b["alpha"]
    size_ia = drop_a["size"]
    size_ib = drop_b["size"]

    n_total = n_a + n_b
    alpha_arith = alpha_a + alpha_b - 1

    # Degree computation
    deg_a = list(block_a["degree_sequence"])  # sorted, but we need per-vertex
    # Actually we need per-vertex degrees, not sorted. Compute from edges.
    deg_a_per = [0] * n_a
    for u, v in block_a["edges"]:
        deg_a_per[u] += 1
        deg_a_per[v] += 1

    deg_b_per = [0] * n_b
    for u, v in block_b["edges"]:
        deg_b_per[u] += 1
        deg_b_per[v] += 1

    ia_verts = set(drop_a["vertices"])
    ib_verts = set(drop_b["vertices"])

    all_degrees = []
    for v in range(n_a):
        d = deg_a_per[v] + (size_ib if v in ia_verts else 0)
        all_degrees.append(d)
    for v in range(n_b):
        d = deg_b_per[v] + (size_ia if v in ib_verts else 0)
        all_degrees.append(d)

    d_max = max(all_degrees)
    num_edges = block_a["num_edges"] + block_b["num_edges"] + size_ia * size_ib

    c_val = compute_c_value(alpha_arith, n_total, d_max)

    return {
        "n_total": n_total,
        "alpha_arithmetic": alpha_arith,
        "d_max": d_max,
        "c_arithmetic": round(c_val, 6) if c_val != float("inf") else None,
        "num_edges": num_edges,
        "degree_sequence": sorted(all_degrees, reverse=True),
    }


def construct_composition_adj(block_a, block_b, drop_a, drop_b):
    """Build full adjacency matrix of the IS-join."""
    n_a, n_b = block_a["n"], block_b["n"]
    n = n_a + n_b
    adj = np.zeros((n, n), dtype=np.bool_)

    # Edges from A
    for u, v in block_a["edges"]:
        adj[u, v] = adj[v, u] = True

    # Edges from B (shifted by n_a)
    for u, v in block_b["edges"]:
        adj[n_a + u, n_a + v] = adj[n_a + v, n_a + u] = True

    # Bipartite edges between I_A and I_B
    for va in drop_a["vertices"]:
        for vb in drop_b["vertices"]:
            adj[va, n_a + vb] = adj[n_a + vb, va] = True

    return adj


def _precompute_entries(library):
    """Precompute per-(block, dropping_set) arrays for vectorized scoring.

    For each pair, stores summary stats that fully determine the IS-join
    c-value without touching per-vertex data at scoring time.
    """
    block_ids = []
    drop_idxs = []
    ns = []
    alphas = []
    max_nids = []  # max degree of vertices NOT in the dropping set
    max_ids = []   # max degree of vertices IN the dropping set
    dss = []       # dropping set size
    num_edges_list = []
    drop_verts_list = []

    for block in library:
        n = block["n"]
        # Compute per-vertex degrees once per block
        deg = [0] * n
        for u, v in block["edges"]:
            deg[u] += 1
            deg[v] += 1

        for di, drop in enumerate(block["alpha_dropping_sets"]):
            is_verts = set(drop["vertices"])
            non_is_degs = [deg[v] for v in range(n) if v not in is_verts]
            is_degs = [deg[v] for v in is_verts]

            block_ids.append(block["block_id"])
            drop_idxs.append(di)
            ns.append(n)
            alphas.append(block["alpha"])
            max_nids.append(max(non_is_degs) if non_is_degs else 0)
            max_ids.append(max(is_degs) if is_degs else 0)
            dss.append(drop["size"])
            num_edges_list.append(block["num_edges"])
            drop_verts_list.append(drop["vertices"])

    entries = {
        "block_id": np.array(block_ids, dtype=np.int32),
        "drop_idx": np.array(drop_idxs, dtype=np.int32),
        "n": np.array(ns, dtype=np.int32),
        "alpha": np.array(alphas, dtype=np.int32),
        "max_nid": np.array(max_nids, dtype=np.int32),
        "max_id": np.array(max_ids, dtype=np.int32),
        "ds": np.array(dss, dtype=np.int32),
        "num_edges": np.array(num_edges_list, dtype=np.int32),
    }
    return entries, drop_verts_list


def enumerate_compositions(library, top_k=10000):
    """Vectorized composition enumeration using numpy broadcasting.

    Scores all M² pairs of (block, dropping_set) entries in batches,
    keeping the top_k compositions by c-value (lowest c = best).
    """
    print("\n" + "=" * 60)
    print("PHASE 2: Enumerating Compositions (vectorized)")
    print("=" * 60)

    entries, drop_verts = _precompute_entries(library)
    M = len(entries["n"])
    total_comps = M * M

    print(f"  Blocks: {len(library)}")
    print(f"  Entry pairs (block, drop_set): {M}")
    print(f"  Total compositions: {total_comps:,}")
    print(f"  Keeping top {top_k}")

    # Cast to float64 for arithmetic
    e_n = entries["n"].astype(np.float64)
    e_alpha = entries["alpha"].astype(np.float64)
    e_max_nid = entries["max_nid"].astype(np.float64)
    e_max_id = entries["max_id"].astype(np.float64)
    e_ds = entries["ds"].astype(np.float64)

    BATCH_SIZE = 2000
    num_batches = (M + BATCH_SIZE - 1) // BATCH_SIZE

    # Accumulate candidates across batches
    cand_c = []
    cand_i = []
    cand_j = []
    total_valid = 0

    for batch_idx in tqdm(range(num_batches), desc="  Composing (vectorized)"):
        i_start = batch_idx * BATCH_SIZE
        i_end = min(i_start + BATCH_SIZE, M)

        # Broadcasting: (B, 1) vs (1, M) → (B, M)
        mn_i = e_max_nid[i_start:i_end, None]
        mi_i = e_max_id[i_start:i_end, None]
        ds_i = e_ds[i_start:i_end, None]
        mn_j = e_max_nid[None, :]
        mi_j = e_max_id[None, :]
        ds_j = e_ds[None, :]

        d_max = np.maximum(
            np.maximum(mn_i, mi_i + ds_j),
            np.maximum(mn_j, mi_j + ds_i),
        )

        valid = d_max > 1.0
        batch_valid = int(valid.sum())
        total_valid += batch_valid

        if batch_valid == 0:
            continue

        alpha_arith = e_alpha[i_start:i_end, None] + e_alpha[None, :] - 1.0
        n_total = e_n[i_start:i_end, None] + e_n[None, :]

        ln_d = np.where(valid, np.log(d_max, where=valid, out=np.ones_like(d_max)), 1.0)
        c = np.where(valid, alpha_arith * d_max / (n_total * ln_d), np.inf)

        # Extract top_k from this batch
        flat_c = c.ravel()
        finite_count = int(np.sum(np.isfinite(flat_c)))
        if finite_count == 0:
            continue

        k_batch = min(top_k, finite_count)
        part_idx = np.argpartition(flat_c, k_batch)[:k_batch]
        batch_cs = flat_c[part_idx]

        # Filter inf
        finite_mask = np.isfinite(batch_cs)
        part_idx = part_idx[finite_mask]
        batch_cs = batch_cs[finite_mask]

        if len(batch_cs) == 0:
            continue

        # Convert flat indices to (global_row, col)
        rows = part_idx // M + i_start
        cols = part_idx % M

        cand_c.append(batch_cs)
        cand_i.append(rows)
        cand_j.append(cols)

    if not cand_c:
        print("\n  No valid compositions found.")
        return [], 0

    # Merge all batch candidates and take global top_k
    all_c = np.concatenate(cand_c)
    all_i = np.concatenate(cand_i)
    all_j = np.concatenate(cand_j)

    if len(all_c) > top_k:
        final_idx = np.argpartition(all_c, top_k)[:top_k]
    else:
        final_idx = np.arange(len(all_c))

    final_c = all_c[final_idx]
    final_i = all_i[final_idx]
    final_j = all_j[final_idx]

    # Sort ascending (best c first)
    sort_order = np.argsort(final_c)
    final_c = final_c[sort_order]
    final_i = final_i[sort_order]
    final_j = final_j[sort_order]

    # Reconstruct full composition dicts for the top_k
    block_map = {b["block_id"]: b for b in library}
    compositions = []

    for idx in range(len(final_c)):
        i, j = int(final_i[idx]), int(final_j[idx])

        bid_a = int(entries["block_id"][i])
        bid_b = int(entries["block_id"][j])
        di_a = int(entries["drop_idx"][i])
        di_b = int(entries["drop_idx"][j])

        block_a = block_map[bid_a]
        block_b = block_map[bid_b]
        da = block_a["alpha_dropping_sets"][di_a]
        db = block_b["alpha_dropping_sets"][di_b]

        # Full per-vertex score for the top candidates
        score = score_composition(block_a, block_b, da, db)

        compositions.append({
            "composition_id": idx,
            "block_A_id": bid_a,
            "block_B_id": bid_b,
            "drop_set_A": da["vertices"],
            "drop_set_B": db["vertices"],
            **score,
        })

    print(f"\n  Total compositions: {total_comps:,}")
    print(f"  Valid (finite c): {total_valid:,}")
    print(f"  Stored (top {top_k}): {len(compositions)}")
    if compositions:
        print(f"  Best c: {compositions[0]['c_arithmetic']:.4f}")
        print(f"  Worst stored c: {compositions[-1]['c_arithmetic']:.4f}")

    return compositions, total_valid


def sat_verify_top(compositions, library, k=50):
    """SAT-verify the top k compositions by c-value."""
    print(f"\n  SAT-verifying top {k} compositions...")
    to_verify = compositions[:k]
    block_map = {b["block_id"]: b for b in library}

    results = []
    for comp in tqdm(to_verify, desc="  SAT verification"):
        a = block_map[comp["block_A_id"]]
        b = block_map[comp["block_B_id"]]
        da = {"vertices": comp["drop_set_A"], "size": len(comp["drop_set_A"])}
        db = {"vertices": comp["drop_set_B"], "size": len(comp["drop_set_B"])}

        adj = construct_composition_adj(a, b, da, db)
        n = adj.shape[0]

        # Verify K4-free
        k4free = is_k4_free(adj)

        # SAT alpha
        alpha_s, sat_time, timed_out = alpha_sat(adj, timeout=120)

        c_sat = None
        if not timed_out and alpha_s > 0:
            d_max = int(adj.sum(axis=1).max())
            c_sat = round(compute_c_value(alpha_s, n, d_max), 6)

        results.append({
            **comp,
            "alpha_sat": alpha_s if not timed_out else None,
            "c_sat": c_sat,
            "sat_time_s": round(sat_time, 3),
            "sat_timed_out": timed_out,
            "k4_free_verified": k4free,
            "alpha_match": (alpha_s == comp["alpha_arithmetic"]) if not timed_out else None,
        })

    # Summary
    verified = [r for r in results if r["alpha_sat"] is not None]
    matches = sum(1 for r in verified if r["alpha_match"])
    mismatches = [r for r in verified if not r["alpha_match"]]

    print(f"\n  SAT verified: {len(verified)}/{len(to_verify)}")
    print(f"  Alpha matches: {matches}/{len(verified)}")
    if mismatches:
        print(f"  *** MISMATCHES: {len(mismatches)} ***")
        for r in mismatches[:5]:
            print(f"    comp {r['composition_id']}: arith={r['alpha_arithmetic']} "
                  f"sat={r['alpha_sat']} (n={r['n_total']})")

    k4_fails = sum(1 for r in results if not r.get("k4_free_verified", True))
    if k4_fails:
        print(f"  *** K4 VIOLATIONS: {k4_fails} ***")
    else:
        print(f"  All K4-free: confirmed")

    return results


# ============================================================================
# Enrichment: promote top compositions to library blocks
# ============================================================================

def run_enrichment_round(library, compositions, round_num, outdir,
                         top_n=30, sat_timeout=120, max_is=10000):
    """Take top compositions, SAT-verify, find α-dropping sets, add to library.

    Returns (enriched_library, enrichment_stats).
    """
    print("\n" + "=" * 60)
    print(f"ENRICHMENT ROUND {round_num}")
    print("=" * 60)

    candidates = compositions[:top_n]
    print(f"  Candidates: {len(candidates)} (top by c)")

    block_map = {b["block_id"]: b for b in library}
    seen_certs = set()
    for b in library:
        # Build canonical cert for existing blocks to deduplicate
        adj = graph6_to_adj(b["g6"])
        seen_certs.add(canonical_cert(adj))

    next_block_id = max(b["block_id"] for b in library) + 1
    new_blocks = []
    stats = {
        "round": round_num,
        "candidates_considered": len(candidates),
        "sat_verified": 0,
        "alpha_match": 0,
        "alpha_mismatch": 0,
        "sat_timeout": 0,
        "k4_violations": 0,
        "dropping_sets_found": 0,
        "no_dropping_sets": 0,
        "duplicates_skipped": 0,
        "blocks_added": 0,
        "new_block_sizes": [],
    }

    for ci, comp in enumerate(tqdm(candidates, desc="  Enrichment")):
        bid_a = comp["block_A_id"]
        bid_b = comp["block_B_id"]
        if bid_a not in block_map or bid_b not in block_map:
            continue

        block_a = block_map[bid_a]
        block_b = block_map[bid_b]
        da = {"vertices": comp["drop_set_A"], "size": len(comp["drop_set_A"])}
        db = {"vertices": comp["drop_set_B"], "size": len(comp["drop_set_B"])}

        adj = construct_composition_adj(block_a, block_b, da, db)
        n = adj.shape[0]

        # K4-free check
        if not is_k4_free(adj):
            stats["k4_violations"] += 1
            continue

        # SAT-verify alpha
        alpha_s, sat_time, timed_out = alpha_sat(adj, timeout=sat_timeout)
        if timed_out:
            stats["sat_timeout"] += 1
            continue
        stats["sat_verified"] += 1

        if alpha_s != comp["alpha_arithmetic"]:
            stats["alpha_mismatch"] += 1
            continue
        stats["alpha_match"] += 1

        # Deduplicate
        cert = canonical_cert(adj)
        if cert in seen_certs:
            stats["duplicates_skipped"] += 1
            continue
        seen_certs.add(cert)

        # Find α-dropping sets
        cap = max_is if n <= 16 else max(max_is // 2, 2000)
        dropping = find_alpha_dropping_sets(adj, alpha_s, max_is=cap)
        if not dropping:
            stats["no_dropping_sets"] += 1
            continue
        stats["dropping_sets_found"] += 1

        # Build new block entry
        g6 = adj_to_graph6(adj)
        degrees = [int(adj[i].sum()) for i in range(n)]
        d_max = max(degrees)
        is_critical = False  # skip expensive check for enriched blocks

        new_block = {
            "block_id": next_block_id,
            "n": n,
            "g6": g6,
            "edges": [[int(i), int(j)] for i in range(n)
                      for j in range(i + 1, n) if adj[i, j]],
            "num_edges": int(adj.sum()) // 2,
            "alpha": alpha_s,
            "is_alpha_critical": is_critical,
            "alpha_dropping_sets": dropping,
            "degree_sequence": sorted(degrees, reverse=True),
            "d_max": d_max,
            "source": f"enrichment_round_{round_num}",
            "parent_composition": {
                "block_A_id": bid_a,
                "block_B_id": bid_b,
                "c_arithmetic": comp["c_arithmetic"],
            },
        }
        new_blocks.append(new_block)
        next_block_id += 1

    stats["blocks_added"] = len(new_blocks)
    stats["new_block_sizes"] = [b["n"] for b in new_blocks]

    # Append to library
    enriched = library + new_blocks
    print(f"\n  SAT verified: {stats['sat_verified']}")
    print(f"  Alpha match: {stats['alpha_match']}")
    print(f"  Alpha mismatch: {stats['alpha_mismatch']}")
    print(f"  SAT timeout: {stats['sat_timeout']}")
    print(f"  Dropping sets found: {stats['dropping_sets_found']}")
    print(f"  No dropping sets: {stats['no_dropping_sets']}")
    print(f"  Duplicates skipped: {stats['duplicates_skipped']}")
    print(f"  New blocks added: {stats['blocks_added']}")
    if new_blocks:
        sizes = [b["n"] for b in new_blocks]
        drops = [len(b["alpha_dropping_sets"]) for b in new_blocks]
        print(f"  New block sizes: {sorted(sizes)}")
        print(f"  Dropping sets per new block: {drops}")
    print(f"  Enriched library: {len(enriched)} blocks")

    # Save
    if outdir:
        lib_path = os.path.join(outdir, f"library_enriched_round{round_num}.json")
        with open(lib_path, "w") as f:
            json.dump(enriched, f, indent=2)
        print(f"  Saved to {lib_path}")

    return enriched, stats


# ============================================================================
# Phase 3: Analysis
# ============================================================================

def analyze(compositions, library, sat_results, total_valid):
    """Compute analysis summary."""
    print("\n" + "=" * 60)
    print("PHASE 3: Analysis")
    print("=" * 60)

    summary = {
        "library_size": len(library),
        "total_alpha_dropping_sets": sum(
            len(b["alpha_dropping_sets"]) for b in library
        ),
        "alpha_critical_count": sum(
            1 for b in library if b["is_alpha_critical"]
        ),
        "total_valid_compositions": total_valid,
        "stored_compositions": len(compositions),
    }

    # Best c by N
    best_by_n = defaultdict(lambda: float("inf"))
    all_by_n = defaultdict(list)
    for comp in compositions:
        n = comp["n_total"]
        c = comp["c_arithmetic"]
        if c is not None:
            best_by_n[n] = min(best_by_n[n], c)
            all_by_n[n].append(c)

    summary["best_c_by_n"] = {
        str(n): {
            "best_c": round(best_by_n[n], 4),
            "count": len(all_by_n[n]),
            "mean_c": round(sum(all_by_n[n]) / len(all_by_n[n]), 4),
        }
        for n in sorted(best_by_n.keys())
    }

    # SAT verification summary
    if sat_results:
        verified = [r for r in sat_results if r["alpha_sat"] is not None]
        summary["sat_verification"] = {
            "total_verified": len(verified),
            "alpha_exact_match": sum(1 for r in verified if r["alpha_match"]),
            "alpha_mismatches": sum(1 for r in verified if not r["alpha_match"]),
            "k4_free_all": all(r.get("k4_free_verified", True) for r in sat_results),
            "mean_sat_time_s": round(
                sum(r["sat_time_s"] for r in sat_results) / len(sat_results), 3
            ) if sat_results else 0,
        }
        if verified:
            gaps = [r["alpha_sat"] - r["alpha_arithmetic"]
                    for r in verified if r["alpha_sat"] is not None]
            summary["sat_verification"]["alpha_gap_distribution"] = dict(
                Counter(gaps)
            )

    # Blocks in good compositions (c < 1.5)
    good_comps = [c for c in compositions if c["c_arithmetic"] and c["c_arithmetic"] < 1.5]
    block_counter = Counter()
    drop_sizes = []
    for comp in good_comps:
        block_counter[comp["block_A_id"]] += 1
        block_counter[comp["block_B_id"]] += 1
        drop_sizes.append(len(comp["drop_set_A"]))
        drop_sizes.append(len(comp["drop_set_B"]))

    block_map = {b["block_id"]: b for b in library}
    top_blocks = block_counter.most_common(20)
    summary["good_compositions"] = {
        "count_c_lt_1_5": len(good_comps),
        "top_blocks": [
            {
                "block_id": bid,
                "count": cnt,
                "n": block_map[bid]["n"],
                "alpha": block_map[bid]["alpha"],
                "d_max": block_map[bid]["d_max"],
                "g6": block_map[bid]["g6"],
            }
            for bid, cnt in top_blocks if bid in block_map
        ],
        "drop_set_size_distribution": dict(Counter(drop_sizes)) if drop_sizes else {},
    }

    # Print summary
    print(f"\n  Library: {summary['library_size']} blocks "
          f"({summary['alpha_critical_count']} alpha-critical)")
    print(f"  Total valid compositions: {total_valid:,}")

    print("\n  Best c by N:")
    # Experiment 1 baselines for comparison
    baselines = {40: 1.45, 60: 1.3, 80: 1.2}
    for n_str, stats in sorted(summary["best_c_by_n"].items(), key=lambda x: int(x[0])):
        n = int(n_str)
        bl = baselines.get(n, None)
        bl_str = f"  (Exp1 baseline ~{bl})" if bl else ""
        print(f"    N={n:3d}: best c = {stats['best_c']:.4f}  "
              f"mean = {stats['mean_c']:.4f}  "
              f"(n={stats['count']}){bl_str}")

    if good_comps:
        print(f"\n  Compositions with c < 1.5: {len(good_comps)}")
        print(f"  Top blocks in good compositions:")
        for entry in summary["good_compositions"]["top_blocks"][:10]:
            print(f"    block {entry['block_id']} (n={entry['n']}, α={entry['alpha']}, "
                  f"d_max={entry['d_max']}): appears {entry['count']} times")

    return summary


def generate_plots(compositions, sat_results, outdir):
    """Generate analysis plots."""
    plots_dir = os.path.join(outdir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    if not compositions:
        print("  No compositions to plot.")
        return

    # Plot 1: c vs N scatter
    fig, ax = plt.subplots(figsize=(10, 6))
    ns = [c["n_total"] for c in compositions if c["c_arithmetic"] is not None]
    cs = [c["c_arithmetic"] for c in compositions if c["c_arithmetic"] is not None]

    ax.scatter(ns, cs, alpha=0.3, s=10, label="All compositions")

    # Overlay SAT-verified
    if sat_results:
        sat_ns = [r["n_total"] for r in sat_results if r["c_sat"] is not None]
        sat_cs = [r["c_sat"] for r in sat_results if r["c_sat"] is not None]
        ax.scatter(sat_ns, sat_cs, color="red", s=40, zorder=5,
                   label="SAT-verified", edgecolors="black", linewidth=0.5)

    ax.set_xlabel("N (total vertices)")
    ax.set_ylabel("c = α·d_max / (N·ln(d_max))")
    ax.set_title("IS-Join Compositions: c vs N")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "c_vs_n.png"), dpi=150)
    plt.close()

    # Plot 2: Best c comparison
    best_by_n = defaultdict(lambda: float("inf"))
    for comp in compositions:
        if comp["c_arithmetic"] is not None:
            best_by_n[comp["n_total"]] = min(
                best_by_n[comp["n_total"]], comp["c_arithmetic"]
            )

    ns_sorted = sorted(best_by_n.keys())
    best_cs = [best_by_n[n] for n in ns_sorted]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(ns_sorted, best_cs, "bo-", label="Block composition (best)", markersize=4)

    # Add Experiment 1 baseline reference
    ax.axhline(y=1.2, color="red", linestyle="--", alpha=0.5,
               label="Exp1 random_edge_capped ~1.2")
    ax.axhline(y=0.77, color="green", linestyle="--", alpha=0.5,
               label="SAT-optimal ~0.77 (N≤22)")

    ax.set_xlabel("N (total vertices)")
    ax.set_ylabel("Best c found")
    ax.set_title("Best c-value by N: Block Composition vs Baselines")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "best_c_comparison.png"), dpi=150)
    plt.close()

    # Plot 3: c histogram
    fig, ax = plt.subplots(figsize=(10, 6))
    finite_cs = [c["c_arithmetic"] for c in compositions
                 if c["c_arithmetic"] is not None and c["c_arithmetic"] < 10]
    if finite_cs:
        ax.hist(finite_cs, bins=100, alpha=0.7, edgecolor="black", linewidth=0.3)
        ax.axvline(x=1.2, color="red", linestyle="--", label="Exp1 baseline ~1.2")
        ax.axvline(x=0.77, color="green", linestyle="--", label="SAT-optimal ~0.77")
    ax.set_xlabel("c = α·d_max / (N·ln(d_max))")
    ax.set_ylabel("Count")
    ax.set_title("Distribution of c-values (IS-Join Compositions)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "c_histogram.png"), dpi=150)
    plt.close()

    print(f"  Plots saved to {plots_dir}/")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Block decomposition experiment for K4-free graphs"
    )
    parser.add_argument("--max-n", type=int, default=8,
                        help="Max block size for geng enumeration (default: 8)")
    parser.add_argument("--include-pareto", action="store_true",
                        help="Include SAT-optimal graphs from pareto data")
    parser.add_argument("--pareto-max-n", type=int, default=15,
                        help="Max N for pareto blocks (default: 15)")
    parser.add_argument("--top-k", type=int, default=10000,
                        help="Keep top K compositions (default: 10000)")
    parser.add_argument("--sat-verify", type=int, default=50,
                        help="SAT-verify top N compositions (default: 50)")
    parser.add_argument("--outdir", default=None,
                        help="Output directory (default: same as script)")
    # Enrichment options
    parser.add_argument("--enrich", action="store_true",
                        help="Run enrichment: promote top compositions to library")
    parser.add_argument("--enrich-rounds", type=int, default=1,
                        help="Number of enrichment rounds (default: 1)")
    parser.add_argument("--enrich-top-n", type=int, default=30,
                        help="Candidates per enrichment round (default: 30)")
    parser.add_argument("--sat-timeout", type=int, default=120,
                        help="SAT timeout per call in seconds (default: 120)")
    parser.add_argument("--load-library", default=None,
                        help="Load existing library.json (skip Phase 1)")
    parser.add_argument("--load-compositions", default=None,
                        help="Load existing compositions.json (skip Phase 2)")
    args = parser.parse_args()

    outdir = args.outdir or os.path.dirname(os.path.abspath(__file__))
    os.makedirs(outdir, exist_ok=True)
    t_start = time.time()

    # ── Phase 1: Build or load library ──────────────────────────
    if args.load_library:
        print(f"Loading library from {args.load_library}")
        with open(args.load_library) as f:
            library = json.load(f)
        print(f"  Loaded {len(library)} blocks")
    else:
        geng_path = find_geng()
        if not geng_path:
            print("ERROR: geng not found. Ensure nauty is installed and on PATH.")
            print("  Try: micromamba run -n funsearch python run_experiment.py")
            sys.exit(1)
        print(f"geng: {geng_path}")

        library = build_library(
            args.max_n, geng_path,
            include_pareto=args.include_pareto,
            pareto_max_n=args.pareto_max_n,
        )

        lib_path = os.path.join(outdir, "library.json")
        with open(lib_path, "w") as f:
            json.dump(library, f, indent=2)
        print(f"\n  Library saved to {lib_path}")

    # Library stats
    lib_stats = {
        "total_blocks": len(library),
        "alpha_critical": sum(1 for b in library if b["is_alpha_critical"]),
        "by_n": {},
    }
    for b in library:
        n = b["n"]
        key = str(n)
        if key not in lib_stats["by_n"]:
            lib_stats["by_n"][key] = {"count": 0, "alpha_critical": 0,
                                       "total_dropping_sets": 0}
        lib_stats["by_n"][key]["count"] += 1
        if b["is_alpha_critical"]:
            lib_stats["by_n"][key]["alpha_critical"] += 1
        lib_stats["by_n"][key]["total_dropping_sets"] += len(
            b["alpha_dropping_sets"]
        )

    stats_path = os.path.join(outdir, "library_stats.json")
    with open(stats_path, "w") as f:
        json.dump(lib_stats, f, indent=2)

    if len(library) == 0:
        print("\nNo blocks found. Nothing to compose.")
        return

    # ── Phase 2: Compose or load compositions ───────────────────
    if args.load_compositions:
        print(f"\nLoading compositions from {args.load_compositions}")
        with open(args.load_compositions) as f:
            compositions = json.load(f)
        total_valid = len(compositions)
        print(f"  Loaded {len(compositions)} compositions")
    else:
        compositions, total_valid = enumerate_compositions(
            library, top_k=args.top_k
        )
        comp_path = os.path.join(outdir, "compositions.json")
        with open(comp_path, "w") as f:
            json.dump(compositions, f, indent=2)
        print(f"  Compositions saved to {comp_path}")

    # SAT-verify top compositions
    sat_results = []
    if compositions and args.sat_verify > 0:
        sat_results = sat_verify_top(
            compositions, library, k=args.sat_verify
        )
        sat_path = os.path.join(outdir, "top50_sat_verified.json")
        with open(sat_path, "w") as f:
            json.dump(sat_results, f, indent=2)
        print(f"  SAT results saved to {sat_path}")

    # ── Phase 3: Analyze round 0 ───────────────────────────────
    summary = analyze(compositions, library, sat_results, total_valid)
    generate_plots(compositions, sat_results, outdir)

    # ── Enrichment rounds ───────────────────────────────────────
    enrichment_summaries = []
    if args.enrich:
        current_library = library
        current_compositions = compositions

        for rnd in range(1, args.enrich_rounds + 1):
            enriched_library, enrich_stats = run_enrichment_round(
                current_library, current_compositions,
                round_num=rnd, outdir=outdir,
                top_n=args.enrich_top_n,
                sat_timeout=args.sat_timeout,
            )
            enrichment_summaries.append(enrich_stats)

            if enrich_stats["blocks_added"] == 0:
                print(f"\n  Round {rnd}: no new blocks added. Stopping.")
                break

            # Rerun composition with enriched library
            new_comps, new_valid = enumerate_compositions(
                enriched_library, top_k=args.top_k
            )
            comp_path = os.path.join(
                outdir, f"compositions_round{rnd}.json"
            )
            with open(comp_path, "w") as f:
                json.dump(new_comps, f, indent=2)

            # SAT-verify top of new compositions
            new_sat = []
            if new_comps and args.sat_verify > 0:
                new_sat = sat_verify_top(
                    new_comps, enriched_library, k=args.sat_verify
                )
                sat_path = os.path.join(
                    outdir, f"top50_round{rnd}_verified.json"
                )
                with open(sat_path, "w") as f:
                    json.dump(new_sat, f, indent=2)

            # Analyze
            round_summary = analyze(
                new_comps, enriched_library, new_sat, new_valid
            )
            generate_plots(new_comps, new_sat, outdir)

            enrich_stats["round_summary"] = round_summary
            current_library = enriched_library
            current_compositions = new_comps

        # Save enrichment summary
        if enrichment_summaries:
            enrich_path = os.path.join(outdir, "enrichment_summary.json")
            with open(enrich_path, "w") as f:
                json.dump(enrichment_summaries, f, indent=2, default=str)
            print(f"\n  Enrichment summary saved to {enrich_path}")

    summary["wall_time_s"] = round(time.time() - t_start, 1)
    if enrichment_summaries:
        summary["enrichment"] = enrichment_summaries

    summary_path = os.path.join(outdir, "analysis_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"\n  Summary saved to {summary_path}")

    print(f"\n  Total wall time: {summary['wall_time_s']:.1f}s")
    print("=" * 60)
    print("DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
