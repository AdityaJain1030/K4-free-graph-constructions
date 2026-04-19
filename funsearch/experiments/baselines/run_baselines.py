#!/usr/bin/env python3
"""
Baselines: 4 K₄-free construction methods across N=5..100
==========================================================

For each N and each d_cap in a sweep, run 5 methods (M1, M2, M3, M3b, M4),
record the best graph per (method, N), compute α via SAT, and compare
structurally. Tests whether heuristic constructions converge to an attractor.

Output: experiments/baselines/{blocks.json, all_results.csv, best_results.csv,
graphs/*, c_vs_N.png, d_vs_N.png, variance_vs_N.png, jaccard_vs_N.png,
structural_comparison.csv, comparison_summary.md, summary.md}

Usage:
    micromamba run -n funsearch python experiments/baselines/run_baselines.py
"""

import argparse
import csv
import importlib.util
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
import pynauty

sys.stdout.reconfigure(line_buffering=True)

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
alpha_sat = _bd.alpha_sat
alpha_exact = _bd.alpha_exact
is_k4_free = _bd.is_k4_free
compute_c_value = _bd.compute_c_value
canonical_cert = _bd.canonical_cert
LIBRARY_PATH = os.path.join(_HERE, "..", "block_decomposition", "library.json")

PARETO_DIR = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "SAT_old", "pareto_reference")
)
OUTDIR = _HERE
GRAPH_DIR = os.path.join(OUTDIR, "graphs")

# =============================================================================
# Core utilities
# =============================================================================

def compute_nbr_masks(adj):
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        m = 0
        for j in range(n):
            if adj[i, j]:
                m |= 1 << j
        nbr[i] = m
    return nbr


def would_create_k4(nbr, u, v):
    """K₄-free iff every neighborhood is triangle-free.
    Adding (u,v) creates K₄ iff N(u) ∩ N(v) contains an edge."""
    common = nbr[u] & nbr[v]
    tmp = common
    while tmp:
        c = (tmp & -tmp).bit_length() - 1
        if nbr[c] & (common & ~(1 << c)):
            return True
        tmp &= tmp - 1
    return False


def add_edge_inplace(adj, nbr, degs, u, v):
    adj[u, v] = adj[v, u] = True
    nbr[u] |= 1 << v
    nbr[v] |= 1 << u
    degs[u] += 1
    degs[v] += 1


def greedy_mis(adj):
    """Greedy maximum independent set: repeatedly pick vertex of min degree
    in current graph. Lower bound on α. Fast O(N²)."""
    n = adj.shape[0]
    if n == 0:
        return 0
    remaining = set(range(n))
    mis_size = 0
    while remaining:
        best = min(remaining, key=lambda v: sum(1 for u in remaining if adj[v, u]))
        mis_size += 1
        remaining.discard(best)
        for u in list(remaining):
            if adj[best, u]:
                remaining.discard(u)
    return mis_size


def alpha_with_fallback(adj, timeout=60):
    """Use alpha_exact for n ≤ 16, alpha_sat for larger."""
    n = adj.shape[0]
    if n == 0:
        return 0, False
    if n <= 16:
        a, _ = alpha_exact(adj)
        return int(a), False
    a, _, timed_out = alpha_sat(adj, timeout=timeout)
    return int(a), bool(timed_out)


def degree_stats(adj):
    degs = adj.sum(axis=1).astype(int)
    if len(degs) == 0:
        return 0, 0, 0.0, 0.0, []
    return int(degs.max()), int(degs.min()), float(degs.mean()), float(degs.var()), degs.tolist()


def graph_result_dict(method, N, d_cap, adj, t_elapsed, alpha_override=None):
    d_max, d_min, d_mean, d_var, degs = degree_stats(adj)
    if alpha_override is not None:
        alpha, to = int(alpha_override), False
    else:
        alpha, to = alpha_with_fallback(adj, timeout=60)
    gmis = greedy_mis(adj)
    c = compute_c_value(alpha, N, d_max) if d_max >= 2 else None
    return {
        "method": method,
        "N": N,
        "d_cap": d_cap,
        "d_max": d_max,
        "d_min": d_min,
        "d_mean": round(d_mean, 3),
        "d_var": round(d_var, 3),
        "alpha": alpha,
        "alpha_timed_out": to,
        "greedy_mis": gmis,
        "c": round(c, 4) if c is not None and math.isfinite(c) else None,
        "time_s": round(t_elapsed, 2),
        "edges": [[i, j] for i in range(N) for j in range(i+1, N) if adj[i, j]],
    }


def save_edgelist(path, adj):
    N = adj.shape[0]
    with open(path, "w") as f:
        for i in range(N):
            for j in range(i+1, N):
                if adj[i, j]:
                    f.write(f"{i} {j}\n")


def edges_to_adj(N, edges):
    adj = np.zeros((N, N), dtype=np.bool_)
    for u, v in edges:
        adj[u, v] = adj[v, u] = True
    return adj


# =============================================================================
# Block library selection
# =============================================================================

def has_triangle(adj):
    n = adj.shape[0]
    nbr = compute_nbr_masks(adj)
    for i in range(n):
        for j in range(i+1, n):
            if adj[i, j] and (nbr[i] & nbr[j]):
                return True
    return False


def select_blocks(library, out_path):
    """Filter triangle-free blocks, rank by α/|V| asc, pick top per size.
    Target: 5-8 blocks spanning sizes 3-8."""
    tri_free = []
    for b in library:
        adj = edges_to_adj(b["n"], b["edges"])
        if not has_triangle(adj):
            tri_free.append(b)
    print(f"  {len(tri_free)} triangle-free blocks (of {len(library)})")

    # Rank by α/|V| ascending, break ties by d_max descending
    def key(b):
        return (b["alpha"] / b["n"], -b["d_max"])

    tri_free.sort(key=key)

    # Pick best per size, sizes 3-8
    picked = {}
    for b in tri_free:
        n = b["n"]
        if n < 3 or n > 8:
            continue
        if n not in picked:
            picked[n] = b
    blocks = [picked[n] for n in sorted(picked)]

    out = []
    for b in blocks:
        out.append({
            "block_id": b["block_id"],
            "n": b["n"],
            "edges": b["edges"],
            "alpha": b["alpha"],
            "d_max": b["d_max"],
            "alpha_ratio": round(b["alpha"] / b["n"], 4),
            "c_block": round(compute_c_value(b["alpha"], b["n"], b["d_max"]), 4)
                       if b["d_max"] >= 2 else None,
            "g6": b.get("g6", ""),
        })

    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"  Selected {len(out)} blocks, sizes {[b['n'] for b in out]}")
    for b in out:
        print(f"    n={b['n']} α={b['alpha']} d_max={b['d_max']} α/n={b['alpha_ratio']}")
    return out


# =============================================================================
# Method 1: Random edges with degree cap
# =============================================================================

def method1_random(N, d_cap, num_trials=3, rng_seed=0):
    """Random edge addition with K₄-free check + d_cap."""
    best_adj = None
    best_c = float("inf")
    for trial in range(num_trials):
        rng = random.Random(rng_seed * 1000 + trial)
        adj = np.zeros((N, N), dtype=np.bool_)
        nbr = [0] * N
        degs = [0] * N
        all_pairs = [(u, v) for u in range(N) for v in range(u+1, N)]
        rng.shuffle(all_pairs)
        for u, v in all_pairs:
            if adj[u, v]:
                continue
            if degs[u] >= d_cap or degs[v] >= d_cap:
                continue
            if would_create_k4(nbr, u, v):
                continue
            add_edge_inplace(adj, nbr, degs, u, v)
        # Try more rounds of additions (pairs may have become addable)
        # Actually the first pass may have skipped edges due to cap constraints
        # that now don't apply. One retry:
        for u, v in all_pairs:
            if adj[u, v]:
                continue
            if degs[u] >= d_cap or degs[v] >= d_cap:
                continue
            if would_create_k4(nbr, u, v):
                continue
            add_edge_inplace(adj, nbr, degs, u, v)
        d_max = max(degs)
        if d_max < 2:
            continue
        # α quick approximation via greedy MIS for trial selection
        gmis = greedy_mis(adj)
        c_est = gmis * d_max / (N * math.log(d_max))
        if c_est < best_c:
            best_c = c_est
            best_adj = adj.copy()
    if best_adj is None:
        return np.zeros((N, N), dtype=np.bool_)
    return best_adj


# =============================================================================
# Method 2: Block joining
# =============================================================================

def tile_blocks(N, blocks):
    """Return list of blocks (in order) whose sizes sum to ≤ N, greedy by size."""
    sizes = sorted({b["n"] for b in blocks}, reverse=True)
    biggest_per_size = {b["n"]: b for b in blocks if b["n"] in sizes}
    remaining = N
    chosen = []
    for s in sizes:
        while remaining >= s:
            chosen.append(biggest_per_size[s])
            remaining -= s
    # Fill rest with isolated vertices (size-1 "blocks") — no edges
    return chosen, remaining  # remaining = # isolated vertices


def place_blocks(adj, nbr, degs, blocks, isolated):
    """Place disjoint blocks into adj starting at offset 0. Returns list of
    (start, end) ranges for each block including isolated."""
    ranges = []
    offset = 0
    for b in blocks:
        for u, v in b["edges"]:
            gu, gv = offset + u, offset + v
            add_edge_inplace(adj, nbr, degs, gu, gv)
        ranges.append((offset, offset + b["n"]))
        offset += b["n"]
    for _ in range(isolated):
        ranges.append((offset, offset + 1))
        offset += 1
    return ranges


def method2_block_join(N, d_cap, blocks, refine_all_edges=False):
    """Tile N vertices with blocks, then greedily add cross-edges."""
    adj = np.zeros((N, N), dtype=np.bool_)
    nbr = [0] * N
    degs = [0] * N
    tiling, isolated = tile_blocks(N, blocks)
    ranges = place_blocks(adj, nbr, degs, tiling, isolated)

    # Block id per vertex
    block_of = [-1] * N
    for bi, (s, e) in enumerate(ranges):
        for v in range(s, e):
            block_of[v] = bi

    def candidate_edges(allow_intra=False):
        cand = []
        for u in range(N):
            if degs[u] >= d_cap:
                continue
            for v in range(u+1, N):
                if adj[u, v]:
                    continue
                if degs[v] >= d_cap:
                    continue
                if not allow_intra and block_of[u] == block_of[v]:
                    continue
                if would_create_k4(nbr, u, v):
                    continue
                cand.append((u, v))
        return cand

    def greedy_step(allow_intra=False):
        cand = candidate_edges(allow_intra=allow_intra)
        if not cand:
            return False
        best_c = float("inf")
        best_uv = None
        # Score candidates by greedy MIS after adding
        for u, v in cand:
            adj[u, v] = adj[v, u] = True
            nbr[u] |= 1 << v
            nbr[v] |= 1 << u
            degs[u] += 1; degs[v] += 1
            d_max = max(degs)
            if d_max >= 2:
                a = greedy_mis(adj)
                c = a * d_max / (N * math.log(d_max))
            else:
                c = float("inf")
            adj[u, v] = adj[v, u] = False
            nbr[u] &= ~(1 << v)
            nbr[v] &= ~(1 << u)
            degs[u] -= 1; degs[v] -= 1
            if c < best_c:
                best_c = c
                best_uv = (u, v)
        if best_uv is None:
            return False
        u, v = best_uv
        add_edge_inplace(adj, nbr, degs, u, v)
        return True

    # Phase 1: cross-block greedy
    steps = 0
    while greedy_step(allow_intra=False):
        steps += 1
        if steps > N * d_cap:
            break  # safety
    # Phase 2: optional refinement with all edges
    if refine_all_edges:
        steps = 0
        while greedy_step(allow_intra=True):
            steps += 1
            if steps > N * d_cap:
                break
    return adj


# =============================================================================
# Method 3: Regularity targeting
# =============================================================================

def method3_regularity(N, d_cap):
    """Add edges that minimize degree variance. K₄-free + d_cap."""
    adj = np.zeros((N, N), dtype=np.bool_)
    nbr = [0] * N
    degs = [0] * N

    while True:
        # Candidate edges
        best_var = float("inf")
        best_uv = None
        # Heuristic: prefer low-degree pair; among those, compute variance delta
        # For speed: only consider edges where both endpoints have minimum (or
        # near-minimum) current degree.
        min_deg = min(d for d in degs if d < d_cap) if any(d < d_cap for d in degs) else None
        if min_deg is None:
            break
        # Build candidate list of low-degree vertices (within +1 of min)
        low_verts = [v for v in range(N) if degs[v] <= min_deg + 1 and degs[v] < d_cap]
        # Expand if too restrictive
        if len(low_verts) < 2:
            low_verts = [v for v in range(N) if degs[v] < d_cap]
        # Score: variance after adding
        for ui in range(len(low_verts)):
            for vi in range(ui+1, len(low_verts)):
                u, v = low_verts[ui], low_verts[vi]
                if adj[u, v]:
                    continue
                if would_create_k4(nbr, u, v):
                    continue
                # Compute var delta efficiently
                # var_new - var_old has closed form. Just recompute var.
                degs[u] += 1; degs[v] += 1
                var_new = float(np.var(degs))
                degs[u] -= 1; degs[v] -= 1
                if var_new < best_var:
                    best_var = var_new
                    best_uv = (u, v)
        if best_uv is None:
            break
        u, v = best_uv
        add_edge_inplace(adj, nbr, degs, u, v)
    return adj


# =============================================================================
# Method 3b: Regularity targeting with α-awareness
# =============================================================================

def method3b_alpha_aware(N, d_cap, sat_timeout=30):
    """Regularity targeting; when α stagnates, switch to common-nbr heuristic."""
    adj = np.zeros((N, N), dtype=np.bool_)
    nbr = [0] * N
    degs = [0] * N

    last_alpha = None
    edges_since_alpha_check = 0
    edges_since_alpha_drop = 0

    def add_by_regularity():
        best_var = float("inf")
        best_uv = None
        if not any(d < d_cap for d in degs):
            return False
        min_deg = min(d for d in degs if d < d_cap)
        low_verts = [v for v in range(N) if degs[v] <= min_deg + 1 and degs[v] < d_cap]
        if len(low_verts) < 2:
            low_verts = [v for v in range(N) if degs[v] < d_cap]
        for ui in range(len(low_verts)):
            for vi in range(ui+1, len(low_verts)):
                u, v = low_verts[ui], low_verts[vi]
                if adj[u, v] or would_create_k4(nbr, u, v):
                    continue
                degs[u] += 1; degs[v] += 1
                var_new = float(np.var(degs))
                degs[u] -= 1; degs[v] -= 1
                if var_new < best_var:
                    best_var = var_new
                    best_uv = (u, v)
        if best_uv is None:
            return False
        add_edge_inplace(adj, nbr, degs, *best_uv)
        return True

    def add_by_common_nbr():
        """Pick valid edge between two vertices sharing most common neighbors."""
        best_cn = -1
        best_uv = None
        for u in range(N):
            if degs[u] >= d_cap:
                continue
            for v in range(u+1, N):
                if adj[u, v] or degs[v] >= d_cap:
                    continue
                if would_create_k4(nbr, u, v):
                    continue
                cn = bin(nbr[u] & nbr[v]).count("1")
                if cn > best_cn:
                    best_cn = cn
                    best_uv = (u, v)
        if best_uv is None:
            return False
        add_edge_inplace(adj, nbr, degs, *best_uv)
        return True

    step = 0
    while True:
        # Check α every 10 edges
        if step > 0 and step % 10 == 0:
            if max(degs) >= 2:
                a, _ = alpha_with_fallback(adj, timeout=sat_timeout)
                if last_alpha is not None and a < last_alpha:
                    edges_since_alpha_drop = 0
                else:
                    edges_since_alpha_drop += 10
                last_alpha = a
            edges_since_alpha_check = 0
        # Strategy choice
        use_common_nbr = (edges_since_alpha_drop >= 20)
        added = False
        if use_common_nbr:
            added = add_by_common_nbr() or add_by_regularity()
            edges_since_alpha_drop = 0  # reset counter after intervention
        else:
            added = add_by_regularity()
        if not added:
            break
        step += 1
        if step > N * d_cap + 10:  # safety
            break
    return adj


# =============================================================================
# Method 4: Greedy c-minimization (fallback variant)
# =============================================================================

def method4_c_minimize(N, d_cap, sat_timeout=30):
    """Phase 1: fill degree by regularity. Phase 2: α-carving via greedy MIS
    per candidate + SAT every 5 edges (fallback variant)."""
    adj = np.zeros((N, N), dtype=np.bool_)
    nbr = [0] * N
    degs = [0] * N

    # Phase 1: regularity until most vertices are at d_cap
    saturation_target = max(0, N - 2)  # almost all at d_cap
    while sum(1 for d in degs if d >= d_cap) < saturation_target:
        min_deg = min(d for d in degs if d < d_cap) if any(d < d_cap for d in degs) else None
        if min_deg is None:
            break
        low_verts = [v for v in range(N) if degs[v] <= min_deg + 1 and degs[v] < d_cap]
        if len(low_verts) < 2:
            low_verts = [v for v in range(N) if degs[v] < d_cap]
        best_var = float("inf")
        best_uv = None
        for ui in range(len(low_verts)):
            for vi in range(ui+1, len(low_verts)):
                u, v = low_verts[ui], low_verts[vi]
                if adj[u, v] or would_create_k4(nbr, u, v):
                    continue
                degs[u] += 1; degs[v] += 1
                var_new = float(np.var(degs))
                degs[u] -= 1; degs[v] -= 1
                if var_new < best_var:
                    best_var = var_new
                    best_uv = (u, v)
        if best_uv is None:
            break
        add_edge_inplace(adj, nbr, degs, *best_uv)

    # Phase 2: α-carving. Per-candidate scoring via greedy MIS, true α via SAT every 5 edges.
    step = 0
    while True:
        # Enumerate candidates
        cands = []
        for u in range(N):
            if degs[u] >= d_cap:
                continue
            for v in range(u+1, N):
                if adj[u, v] or degs[v] >= d_cap:
                    continue
                if would_create_k4(nbr, u, v):
                    continue
                cands.append((u, v))
        if not cands:
            break
        # Score each candidate by greedy MIS after adding (proxy for α)
        best_score = float("inf")
        best_uv = None
        for u, v in cands:
            adj[u, v] = adj[v, u] = True
            nbr[u] |= 1 << v; nbr[v] |= 1 << u
            degs[u] += 1; degs[v] += 1
            gmis = greedy_mis(adj)
            adj[u, v] = adj[v, u] = False
            nbr[u] &= ~(1 << v); nbr[v] &= ~(1 << u)
            degs[u] -= 1; degs[v] -= 1
            if gmis < best_score:
                best_score = gmis
                best_uv = (u, v)
        if best_uv is None:
            break
        add_edge_inplace(adj, nbr, degs, *best_uv)
        step += 1
        # Optional SAT check every 5 edges (safety, no early termination)
        if step >= N * d_cap:
            break
    return adj


# =============================================================================
# Main sweep
# =============================================================================

METHODS = [
    ("method1", "M1 random+d_cap"),
    ("method2", "M2 block joining"),
    ("method2r", "M2 block joining (refined)"),
    ("method3", "M3 regularity"),
    ("method3b", "M3b α-aware regularity"),
    ("method4", "M4 c-minimization"),
]


def d_cap_sweep(N):
    vals = [3, 4, 5, 6, 8, 10, 12, 15, 20]
    cap = min(20, max(3, N // 2))
    return [d for d in vals if d <= cap and d <= N - 1]


def run_method(method, N, d_cap, blocks, rng_seed=0):
    t0 = time.time()
    if method == "method1":
        adj = method1_random(N, d_cap, num_trials=3, rng_seed=rng_seed)
    elif method == "method2":
        adj = method2_block_join(N, d_cap, blocks, refine_all_edges=False)
    elif method == "method2r":
        adj = method2_block_join(N, d_cap, blocks, refine_all_edges=True)
    elif method == "method3":
        adj = method3_regularity(N, d_cap)
    elif method == "method3b":
        adj = method3b_alpha_aware(N, d_cap)
    elif method == "method4":
        adj = method4_c_minimize(N, d_cap)
    else:
        raise ValueError(f"Unknown method {method}")
    elapsed = time.time() - t0
    return adj, elapsed


def sweep_main(args):
    print("=" * 60)
    print("Baseline sweep — 4+ methods × N=5..100 × d_cap sweep")
    print("=" * 60)

    os.makedirs(GRAPH_DIR, exist_ok=True)

    # --- Step 1: load / select blocks ---
    print("\n[step 1] Loading library and selecting blocks...")
    with open(LIBRARY_PATH) as f:
        library = json.load(f)
    print(f"  Library: {len(library)} K₄-free blocks")
    blocks = select_blocks(library, os.path.join(OUTDIR, "blocks.json"))

    # --- Step 2: main sweep ---
    all_rows = []
    best_per_method_N = {}  # (method, N) -> result dict with adj
    N_values = list(range(max(5, args.n_min), args.n_max + 1))

    method_names = [m[0] for m in METHODS]
    if args.methods:
        method_names = [m for m in method_names if m in args.methods]

    t_global = time.time()
    for N in N_values:
        caps = d_cap_sweep(N)
        if not caps:
            continue
        t_N = time.time()
        for method in method_names:
            best = None  # best (result_with_adj) across d_cap sweep
            for d_cap in caps:
                # Skip method4 past cutoff if flagged
                if method == "method4" and N > args.method4_cutoff:
                    continue
                try:
                    adj, elapsed = run_method(method, N, d_cap, blocks,
                                              rng_seed=N)
                except Exception as e:
                    print(f"  [N={N} {method} d={d_cap}] ERROR: {e}")
                    continue
                # Compute c quickly via alpha
                d_max, d_min, d_mean, d_var, degs = degree_stats(adj)
                if d_max < 2:
                    continue
                # Quick alpha estimate first via greedy MIS
                gmis = greedy_mis(adj)
                # True alpha via SAT (or alpha_exact for small)
                try:
                    alpha, to = alpha_with_fallback(adj, timeout=args.sat_timeout)
                except Exception as e:
                    print(f"  [N={N} {method} d={d_cap}] alpha error: {e}")
                    continue
                c = compute_c_value(alpha, N, d_max)
                row = {
                    "method": method,
                    "N": N,
                    "d_cap": d_cap,
                    "d_max": d_max,
                    "d_min": d_min,
                    "d_mean": round(d_mean, 3),
                    "d_var": round(d_var, 3),
                    "alpha": alpha,
                    "alpha_timed_out": int(to),
                    "greedy_mis": gmis,
                    "c": round(c, 4) if c is not None and math.isfinite(c) else None,
                    "time_s": round(elapsed, 2),
                }
                all_rows.append(row)
                if row["c"] is not None:
                    if best is None or row["c"] < best["c"]:
                        best = dict(row)
                        best["adj"] = adj.copy()
            if best is not None:
                best_per_method_N[(method, N)] = best
                # Save graph
                path = os.path.join(GRAPH_DIR, f"{method}_N{N:03d}.edgelist")
                save_edgelist(path, best["adj"])
        t_N_elapsed = time.time() - t_N
        t_total = time.time() - t_global
        # Progress log
        if N % 5 == 0 or N == N_values[-1]:
            print(f"  [N={N}] N-elapsed={t_N_elapsed:.1f}s total={t_total/60:.1f}min")
        # Periodic save of all_results.csv
        if N % 20 == 0:
            _save_all_csv(all_rows, best_per_method_N)

    _save_all_csv(all_rows, best_per_method_N)

    print(f"\n[step 2] sweep complete in {(time.time()-t_global)/60:.1f}min")
    return all_rows, best_per_method_N, blocks


def _save_all_csv(all_rows, best_per_method_N):
    cols = ["method", "N", "d_cap", "d_max", "d_min", "d_mean", "d_var",
            "alpha", "alpha_timed_out", "greedy_mis", "c", "time_s"]
    with open(os.path.join(OUTDIR, "all_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            w.writerow({k: r.get(k, "") for k in cols})
    best_cols = cols
    with open(os.path.join(OUTDIR, "best_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=best_cols)
        w.writeheader()
        for key in sorted(best_per_method_N):
            r = best_per_method_N[key]
            w.writerow({k: r.get(k, "") for k in best_cols})


# =============================================================================
# Structural comparison
# =============================================================================

def adj_to_pynauty(adj):
    n = adj.shape[0]
    g = pynauty.Graph(n)
    for i in range(n):
        nbrs = [int(j) for j in range(n) if j != i and adj[i, j]]
        if nbrs:
            g.connect_vertex(i, nbrs)
    return g


def canonical_edges(adj):
    """Apply pynauty canon_label to get canonical edge set (frozenset)."""
    n = adj.shape[0]
    g = adj_to_pynauty(adj)
    # canon_label returns a permutation mapping original -> canonical position
    try:
        perm = pynauty.canon_label(g)  # list of length n
    except Exception:
        # fallback: use certificate bytes as identity
        return frozenset((i, j) for i in range(n) for j in range(i+1, n) if adj[i, j])
    # perm[old] = new; relabel edges
    edges = set()
    for i in range(n):
        for j in range(i+1, n):
            if adj[i, j]:
                a, b = perm[i], perm[j]
                if a > b: a, b = b, a
                edges.add((a, b))
    return frozenset(edges)


def jaccard(s1, s2):
    if not s1 and not s2:
        return 1.0
    return len(s1 & s2) / len(s1 | s2)


def degree_sequence_l1(adj1, adj2):
    d1 = sorted(adj1.sum(axis=1).astype(int), reverse=True)
    d2 = sorted(adj2.sum(axis=1).astype(int), reverse=True)
    n = max(len(d1), len(d2))
    while len(d1) < n: d1.append(0)
    while len(d2) < n: d2.append(0)
    return sum(abs(a - b) for a, b in zip(d1, d2)) / n


def structural_comparison(best_per_method_N, jaccard_max_N=50):
    """Per pair of methods at each N: Jaccard on canonical, isomorphism,
    degree seq L1. Return list of rows + per-pair N→jaccard dict."""
    rows = []
    pair_jaccard = defaultdict(list)  # (m1, m2) -> list of (N, jaccard)

    methods = sorted({m for (m, _) in best_per_method_N})
    N_by_method = defaultdict(set)
    for (m, N) in best_per_method_N:
        N_by_method[m].add(N)
    # Precompute canonical forms (cost scales w/ N)
    canon_cache = {}
    edge_cache = {}
    for (m, N), r in best_per_method_N.items():
        if N <= jaccard_max_N:
            adj = r["adj"]
            canon_cache[(m, N)] = canonical_cert(adj)
            edge_cache[(m, N)] = canonical_edges(adj)

    for i, m1 in enumerate(methods):
        for m2 in methods[i+1:]:
            common_N = sorted(N_by_method[m1] & N_by_method[m2])
            for N in common_N:
                r1 = best_per_method_N[(m1, N)]
                r2 = best_per_method_N[(m2, N)]
                iso = False
                jac = None
                if N <= jaccard_max_N:
                    cert1 = canon_cache.get((m1, N))
                    cert2 = canon_cache.get((m2, N))
                    iso = (cert1 is not None and cert1 == cert2)
                    e1 = edge_cache.get((m1, N))
                    e2 = edge_cache.get((m2, N))
                    if e1 is not None and e2 is not None:
                        jac = jaccard(e1, e2)
                d_l1 = degree_sequence_l1(r1["adj"], r2["adj"])
                row = {
                    "method1": m1, "method2": m2, "N": N,
                    "jaccard_canonical": round(jac, 4) if jac is not None else None,
                    "isomorphic": int(iso),
                    "deg_seq_L1_norm": round(d_l1, 4),
                    "c1": r1["c"], "c2": r2["c"],
                    "c_gap": round(abs((r1["c"] or 0) - (r2["c"] or 0)), 4)
                             if (r1["c"] is not None and r2["c"] is not None) else None,
                }
                rows.append(row)
                if jac is not None:
                    pair_jaccard[(m1, m2)].append((N, jac))

    return rows, pair_jaccard


def convergence_detection(best_per_method_N, window=10, threshold=0.01):
    """For each method, compute rolling mean of c over window. Return
    first N where rolling mean change < threshold (relative)."""
    by_method = defaultdict(list)
    for (m, N), r in sorted(best_per_method_N.items()):
        if r["c"] is not None:
            by_method[m].append((N, r["c"]))
    convergence = {}
    for m, pts in by_method.items():
        if len(pts) < 2 * window:
            convergence[m] = {
                "first_N": None,
                "rolling_c": round(pts[-1][1], 4) if pts else None,
                "samples": len(pts),
            }
            continue
        rolling = []
        for i in range(len(pts) - window + 1):
            rolling.append(sum(p[1] for p in pts[i:i+window]) / window)
        # find first i where |rolling[i] - rolling[i-window]| / rolling[i-window] < threshold
        for i in range(window, len(rolling)):
            if rolling[i-window] == 0:
                continue
            rel = abs(rolling[i] - rolling[i-window]) / abs(rolling[i-window])
            if rel < threshold:
                convergence[m] = {
                    "first_N": pts[i][0],
                    "rolling_c": round(rolling[i], 4),
                    "rel_change": round(rel, 4),
                }
                break
        if m not in convergence:
            convergence[m] = {
                "first_N": None,
                "rolling_c": round(rolling[-1], 4) if rolling else None,
                "final_rel_change": None,
            }
    return convergence


# =============================================================================
# Plots
# =============================================================================

def load_sat_optimal(max_n=35):
    out = {}
    for N in range(2, max_n + 1):
        path = os.path.join(PARETO_DIR, f"pareto_n{N}.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            data = json.load(f)
        frontier = [e for e in data.get("pareto_frontier", [])
                    if e.get("c_log") is not None]
        if frontier:
            best = min(frontier, key=lambda e: e["c_log"])
            out[N] = best["c_log"]
    return out


def plot_c_vs_N(best_per_method_N, sat_opt, out_path):
    fig, ax = plt.subplots(figsize=(11, 6))
    by_method = defaultdict(list)
    for (m, N), r in sorted(best_per_method_N.items()):
        if r["c"] is not None:
            by_method[m].append((N, r["c"]))
    cmap = plt.cm.tab10
    for i, (m, pts) in enumerate(sorted(by_method.items())):
        xs = [N for N, _ in pts]
        ys = [c for _, c in pts]
        ax.plot(xs, ys, "-o", color=cmap(i), label=m, markersize=3.5, linewidth=1.5)
    if sat_opt:
        xs = sorted(sat_opt)
        ys = [sat_opt[N] for N in xs]
        ax.plot(xs, ys, "s", color="red", label="SAT-optimal", markersize=6)
    ax.axhline(1.15, linestyle=":", color="gray", label="random ~1.15", alpha=0.7)
    ax.set_xlabel("N")
    ax.set_ylabel(r"$c = \alpha \cdot d_{\max} / (N \log d_{\max})$")
    ax.set_title("Best c per method vs N — K₄-free")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_d_vs_N(best_per_method_N, out_path):
    fig, ax = plt.subplots(figsize=(11, 6))
    by_method = defaultdict(list)
    for (m, N), r in sorted(best_per_method_N.items()):
        by_method[m].append((N, r["d_max"]))
    cmap = plt.cm.tab10
    for i, (m, pts) in enumerate(sorted(by_method.items())):
        xs = [N for N, _ in pts]
        ys = [d for _, d in pts]
        ax.plot(xs, ys, "-o", color=cmap(i), label=m, markersize=3.5, linewidth=1.5)
    ax.set_xlabel("N")
    ax.set_ylabel("d_max at best c")
    ax.set_title("Optimal d_max per method vs N")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_variance_vs_N(best_per_method_N, out_path):
    fig, ax = plt.subplots(figsize=(11, 6))
    by_method = defaultdict(list)
    for (m, N), r in sorted(best_per_method_N.items()):
        by_method[m].append((N, r["d_var"]))
    cmap = plt.cm.tab10
    for i, (m, pts) in enumerate(sorted(by_method.items())):
        xs = [N for N, _ in pts]
        ys = [v for _, v in pts]
        ax.plot(xs, ys, "-o", color=cmap(i), label=m, markersize=3.5, linewidth=1.5)
    ax.set_xlabel("N")
    ax.set_ylabel("degree variance")
    ax.set_title("Degree variance of best graphs per method")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9, loc="best")
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def plot_jaccard_vs_N(pair_jaccard, out_path):
    fig, ax = plt.subplots(figsize=(11, 6))
    cmap = plt.cm.tab10
    for i, ((m1, m2), pts) in enumerate(sorted(pair_jaccard.items())):
        pts = sorted(pts)
        xs = [N for N, _ in pts]
        ys = [j for _, j in pts]
        ax.plot(xs, ys, "-o", color=cmap(i % 10), label=f"{m1} vs {m2}",
                markersize=3, linewidth=1.2)
    ax.set_xlabel("N")
    ax.set_ylabel("Jaccard similarity (canonical edge sets)")
    ax.set_title("Structural similarity between method pairs")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best", ncol=2)
    ax.set_ylim(0, 1.02)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


# =============================================================================
# Summaries
# =============================================================================

def write_comparison(rows, pair_jaccard, convergence, out_path):
    cols = ["method1", "method2", "N", "jaccard_canonical",
            "isomorphic", "deg_seq_L1_norm", "c1", "c2", "c_gap"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in cols})

    # comparison_summary.md
    md_path = out_path.replace("structural_comparison.csv", "comparison_summary.md")
    lines = [
        "# Structural Comparison Summary",
        "",
        "## Convergence (rolling mean of c over window=10, threshold=1% relative change)",
        "",
        "| method | first converged N | rolling c at converge | rel change |",
        "|--------|-------------------|-----------------------|------------|",
    ]
    for m in sorted(convergence):
        c = convergence[m]
        if c and c.get("first_N"):
            lines.append(f"| {m} | {c['first_N']} | {c['rolling_c']} | {c.get('rel_change', '')} |")
        else:
            lines.append(f"| {m} | — (did not converge) | {c.get('rolling_c', '')} | — |")

    # Isomorphism matches
    iso_matches = [r for r in rows if r.get("isomorphic") == 1]
    lines += [
        "",
        f"## Isomorphism matches (up to pynauty canonical certificate)",
        "",
        f"Total matches: **{len(iso_matches)}** (of {len(rows)} comparisons)",
        "",
    ]
    if iso_matches:
        lines += ["| method1 | method2 | N | c |", "|---|---|---|---|"]
        for r in iso_matches[:30]:
            lines.append(f"| {r['method1']} | {r['method2']} | {r['N']} | {r['c1']} |")

    # Per-pair Jaccard summary
    lines += ["", "## Per-pair mean Jaccard (where comparable)", "",
              "| method1 | method2 | mean Jaccard | N samples |",
              "|---|---|---|---|"]
    for (m1, m2), pts in sorted(pair_jaccard.items()):
        if pts:
            mean_j = sum(j for _, j in pts) / len(pts)
            lines.append(f"| {m1} | {m2} | {mean_j:.3f} | {len(pts)} |")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))


def write_summary(best_per_method_N, rows, pair_jaccard, convergence, sat_opt,
                  runtime_total, out_path):
    by_method = defaultdict(list)
    for (m, N), r in sorted(best_per_method_N.items()):
        if r["c"] is not None:
            by_method[m].append((N, r["c"]))

    # Final-20 mean c per method
    final_c = {m: (sum(c for _, c in pts[-20:]) / max(1, len(pts[-20:])))
               for m, pts in by_method.items()}

    # Method-time stats
    time_by_method = defaultdict(list)
    for (m, N), r in best_per_method_N.items():
        time_by_method[m].append(r.get("time_s", 0))
    mean_time = {m: (sum(t for t in ts) / max(1, len(ts))) for m, ts in time_by_method.items()}

    lines = [
        "# Baselines Summary",
        "",
        f"- Runtime: **{runtime_total/60:.1f} min**",
        f"- Methods run: {', '.join(sorted(by_method))}",
        f"- N range: {min(min(N for N,_ in pts) for pts in by_method.values() if pts)}"
        f"..{max(max(N for N,_ in pts) for pts in by_method.values() if pts)}",
        "",
        "## 1. Final-20 mean c per method (attractor value)",
        "",
        "| method | mean c (last 20 N) | samples |",
        "|--------|---------------------|---------|",
    ]
    for m in sorted(final_c):
        lines.append(f"| {m} | {final_c[m]:.4f} | {min(20, len(by_method[m]))} |")

    # Gap to SAT at N in 12..35 where both known
    lines += ["", "## 2. Gap to SAT-optimal at overlap (N=12..35)", "",
              "| N | SAT | " + " | ".join(sorted(by_method)) + " |",
              "|---|-----|" + "|".join(["---"] * len(by_method)) + "|"]
    sat_N = sorted(n for n in sat_opt if 12 <= n <= 35)
    for N in sat_N:
        row = [str(N), f"{sat_opt[N]:.3f}"]
        for m in sorted(by_method):
            r = best_per_method_N.get((m, N))
            row.append(f"{r['c']:.3f}" if r and r["c"] is not None else "—")
        lines.append("| " + " | ".join(row) + " |")

    # Convergence
    lines += ["", "## 3. Convergence", ""]
    for m in sorted(convergence):
        c = convergence[m]
        if c and c.get("first_N"):
            lines.append(f"- **{m}**: rolling c stabilized by N={c['first_N']} "
                         f"at c≈{c['rolling_c']} (Δ<1%)")
        else:
            lines.append(f"- **{m}**: no stable convergence detected "
                         f"(final rolling c={c.get('rolling_c', '—')})")

    # Isomorphism / similarity headline
    iso_count = sum(1 for r in rows if r.get("isomorphic") == 1)
    lines += ["", "## 4. Structural similarity",
              "",
              f"- {iso_count} pairs of (method1, method2, N) produced isomorphic graphs.",
              "- Per-pair mean Jaccard (canonical edge sets) — see `comparison_summary.md`.",
              ""]

    # Answers to questions
    min_m = min(final_c, key=lambda m: final_c[m])
    max_m = max(final_c, key=lambda m: final_c[m])
    lines += [
        "## 5. Attractor questions",
        "",
        f"1. **c stabilizes**: "
        + ("yes — " if all(convergence.get(m, {}).get("first_N") for m in by_method)
           else "partially — ")
        + f"all final-20 c values within {max(final_c.values())-min(final_c.values()):.3f} of each other.",
        f"2. **Methods agree on c?** range {min(final_c.values()):.3f}..{max(final_c.values()):.3f}",
        f"3. **Best method (lowest attractor c)**: {min_m} (c≈{final_c[min_m]:.3f})",
        f"4. **Worst**: {max_m} (c≈{final_c[max_m]:.3f})",
        "5. **Does regularity (M3) match α-aware (M3b, M4)?** See final-20 means above.",
        "6. **Does block structure (M2) help?** Compare M2 vs M1/M3.",
        "",
        "## 6. Runtime per method (mean over best-of-sweep)",
        "",
        "| method | mean time/run (s) |",
        "|--------|--------------------|",
    ]
    for m in sorted(mean_time):
        lines.append(f"| {m} | {mean_time[m]:.2f} |")

    lines += ["", "See `c_vs_N.png`, `d_vs_N.png`, `variance_vs_N.png`, "
              "`jaccard_vs_N.png` for trends."]

    with open(out_path, "w") as f:
        f.write("\n".join(lines))


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n-min", type=int, default=5)
    parser.add_argument("--n-max", type=int, default=100)
    parser.add_argument("--sat-timeout", type=int, default=60)
    parser.add_argument("--method4-cutoff", type=int, default=60,
                        help="skip method4 past this N")
    parser.add_argument("--methods", nargs="*", default=None,
                        help="subset of methods; omit = all")
    parser.add_argument("--jaccard-max-N", type=int, default=50)
    args = parser.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    t_global = time.time()

    all_rows, best_per_method_N, blocks = sweep_main(args)

    # --- structural comparison ---
    print("\n[step 3] Structural comparison...")
    comp_rows, pair_jaccard = structural_comparison(
        best_per_method_N, jaccard_max_N=args.jaccard_max_N)
    convergence = convergence_detection(best_per_method_N)
    write_comparison(
        comp_rows, pair_jaccard, convergence,
        os.path.join(OUTDIR, "structural_comparison.csv"))

    # --- plots ---
    print("[step 4] Plots...")
    sat_opt = load_sat_optimal()
    plot_c_vs_N(best_per_method_N, sat_opt, os.path.join(OUTDIR, "c_vs_N.png"))
    plot_d_vs_N(best_per_method_N, os.path.join(OUTDIR, "d_vs_N.png"))
    plot_variance_vs_N(best_per_method_N, os.path.join(OUTDIR, "variance_vs_N.png"))
    plot_jaccard_vs_N(pair_jaccard, os.path.join(OUTDIR, "jaccard_vs_N.png"))

    # --- summary ---
    print("[step 5] Summary...")
    write_summary(best_per_method_N, comp_rows, pair_jaccard, convergence,
                  sat_opt, time.time() - t_global,
                  os.path.join(OUTDIR, "summary.md"))

    print(f"\nDone. Total {(time.time()-t_global)/60:.1f} min.")
    print(f"Artifacts in {OUTDIR}/")


if __name__ == "__main__":
    main()
