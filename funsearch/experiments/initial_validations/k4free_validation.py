#!/usr/bin/env python3
"""
k4free_validation.py
====================
Pre-FunSearch validation experiment (Experiment 1).

Builds K₄-free graphs at various N using multiple construction methods,
computes exact independence number α via SAT (binary search with PySAT),
compares against cheap proxy estimates (Caro-Wei, greedy MIS), and
measures rank correlation to determine if surrogate scoring is viable.

Usage
-----
# Quick smoke test (N=12, 2 graphs per config)
python k4free_validation.py --quick

# Full experiment
python k4free_validation.py --sizes 40 60 80 --graphs-per-config 10

# Custom run
python k4free_validation.py --sizes 40 60 --methods degree random --workers 4
"""

import argparse
import json
import math
import os
import random
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from itertools import combinations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from tqdm import tqdm

from pysat.card import CardEnc, EncType
from pysat.solvers import Glucose4

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)


# ============================================================================
# Graph representation
# ============================================================================

class K4FreeGraph:
    """Adjacency-matrix graph with degree tracking."""

    def __init__(self, n):
        self.n = n
        self.adj = np.zeros((n, n), dtype=np.bool_)
        self.degree = np.zeros(n, dtype=np.int32)
        self.num_edges = 0

    def copy(self):
        g = K4FreeGraph.__new__(K4FreeGraph)
        g.n = self.n
        g.adj = self.adj.copy()
        g.degree = self.degree.copy()
        g.num_edges = self.num_edges
        return g

    def has_edge(self, u, v):
        return self.adj[u, v]

    def neighbors(self, v):
        return np.where(self.adj[v])[0]

    def common_neighbors(self, u, v):
        return np.where(self.adj[u] & self.adj[v])[0]

    def codegree(self, u, v):
        return int(np.sum(self.adj[u] & self.adj[v]))

    def add_edge(self, u, v):
        self.adj[u, v] = True
        self.adj[v, u] = True
        self.degree[u] += 1
        self.degree[v] += 1
        self.num_edges += 1

    def max_degree(self):
        return int(np.max(self.degree)) if self.n > 0 else 0

    def edge_list(self):
        rows, cols = np.where(np.triu(self.adj, k=1))
        return list(zip(rows.tolist(), cols.tolist()))


# ============================================================================
# K4-freeness checks
# ============================================================================

def would_create_k4(g, u, v):
    """Check if adding edge (u,v) would create a K4.
    K4 is created iff two common neighbors of u,v are adjacent."""
    cn = g.common_neighbors(u, v)
    if len(cn) < 2:
        return False
    sub = g.adj[np.ix_(cn, cn)]
    return bool(np.any(np.triu(sub, k=1)))


def verify_k4_free(adj):
    """Full K4-freeness verification using bitmask scan.
    Returns True if graph is K4-free."""
    n = adj.shape[0]
    # Build bitmask neighbor sets
    nbr = np.zeros(n, dtype=np.uint64) if n <= 64 else [0] * n
    if n <= 64:
        for i in range(n):
            mask = 0
            for j in range(n):
                if adj[i, j]:
                    mask |= (1 << j)
            nbr[i] = mask
    else:
        # For n > 64, use set-based approach
        nbr = [set(np.where(adj[i])[0]) for i in range(n)]

    if n <= 64:
        for a in range(n):
            for b in range(a + 1, n):
                if not adj[a, b]:
                    continue
                common = int(nbr[a]) & int(nbr[b])
                # Remove bits <= b to avoid duplicate counting
                common &= ~((1 << (b + 1)) - 1)
                while common:
                    c = (common & -common).bit_length() - 1
                    # Check if any vertex > c in common is also neighbor of c
                    rest = common & ~(1 << c)
                    rest_and_c_nbr = rest & int(nbr[c])
                    if rest_and_c_nbr:
                        return False
                    common ^= (common & -common)
    else:
        for a in range(n):
            for b in range(a + 1, n):
                if not adj[a, b]:
                    continue
                common = nbr[a] & nbr[b]
                common = {c for c in common if c > b}
                common_list = sorted(common)
                for i, c in enumerate(common_list):
                    for d in common_list[i + 1:]:
                        if adj[c, d]:
                            return False
    return True


# ============================================================================
# Graph construction methods
# ============================================================================

def build_vertex_by_vertex(n, priority_name, seed):
    """Build a K4-free graph by adding vertices one at a time.
    For each new vertex k, greedily connect it to existing vertices
    in priority order, skipping connections that would create K4."""
    rng = random.Random(seed)
    g = K4FreeGraph(n)

    for k in range(1, n):
        # Score all existing vertices
        scores = []
        for v in range(k):
            if priority_name == "degree":
                score = g.degree[v]
            elif priority_name == "inverse_degree":
                score = -g.degree[v]
            elif priority_name == "random":
                score = rng.random()
            elif priority_name == "balanced":
                score = g.degree[v] - 0.5 * g.codegree(v, k)
            else:
                raise ValueError(f"Unknown priority: {priority_name}")
            scores.append((score, v))

        # Sort by decreasing priority (break ties randomly)
        scores.sort(key=lambda x: (-x[0], rng.random()))

        # Greedily connect k to highest-priority vertices
        for _, v in scores:
            if not would_create_k4(g, k, v):
                g.add_edge(k, v)

    return g


def build_random_edge(n, seed, degree_cap=None):
    """Build a K4-free graph by adding random edges.
    Generate all possible edges, shuffle, and add each if K4-free."""
    rng = random.Random(seed)
    g = K4FreeGraph(n)

    # Generate all possible edges
    edges = [(i, j) for i in range(n) for j in range(i + 1, n)]
    rng.shuffle(edges)

    for u, v in edges:
        if degree_cap is not None:
            if g.degree[u] >= degree_cap or g.degree[v] >= degree_cap:
                continue
        if not would_create_k4(g, u, v):
            g.add_edge(u, v)

    return g


# ============================================================================
# Scoring: SAT-based exact independence number
# ============================================================================

def alpha_sat(adj, timeout=300):
    """Compute exact independence number via SAT binary search.
    Uses PySAT Glucose4 with totalizer cardinality encoding.

    Returns (alpha, solve_time_seconds, timed_out).
    """
    n = adj.shape[0]
    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                edges.append((i, j))

    t0 = time.time()

    # Binary search: find largest k where IS of size k exists
    lo, hi = 1, n
    best_alpha = 0
    total_timed_out = False

    while lo <= hi:
        mid = (lo + hi) // 2
        sat, timed_out = _sat_check_is(n, edges, mid, timeout)

        if timed_out:
            total_timed_out = True
            # If timed out, be conservative: assume mid works (IS might exist)
            # but don't increase lo — just try lower
            hi = mid - 1
            continue

        if sat:
            best_alpha = mid
            lo = mid + 1
        else:
            hi = mid - 1

    elapsed = time.time() - t0
    return best_alpha, elapsed, total_timed_out


def _sat_check_is(n, edges, k, timeout):
    """Check if graph has an independent set of size >= k.
    Variables: 1..n (vertex i+1 is in the IS).
    Returns (satisfiable: bool, timed_out: bool)."""
    solver = Glucose4()
    try:
        # Edge constraints: no two adjacent vertices both in IS
        for i, j in edges:
            solver.add_clause([-(i + 1), -(j + 1)])

        # Cardinality constraint: at least k vertices selected
        lits = list(range(1, n + 1))
        cnf = CardEnc.atleast(lits, bound=k, top_id=n, encoding=EncType.totalizer)
        for cl in cnf.clauses:
            solver.add_clause(cl)

        # Solve with timeout
        timed_out_flag = [False]

        def on_timeout():
            timed_out_flag[0] = True
            solver.interrupt()

        timer = threading.Timer(timeout, on_timeout)
        timer.start()
        result = solver.solve_limited()
        timer.cancel()

        if timed_out_flag[0] or result is None:
            return False, True

        return bool(result), False
    finally:
        solver.delete()


# ============================================================================
# Scoring: cheap proxies
# ============================================================================

def caro_wei_bound(g):
    """Caro-Wei lower bound on independence number:
    α(G) >= Σ 1/(d(v)+1)"""
    return float(np.sum(1.0 / (g.degree + 1)))


def greedy_mis(adj, n_restarts=20, seed=0):
    """Greedy maximum independent set with random restarts.
    Returns the size of the largest IS found (lower bound on α)."""
    n = adj.shape[0]
    rng = random.Random(seed)
    best = 0

    # Precompute neighbor sets
    nbr_sets = [set(np.where(adj[i])[0]) for i in range(n)]

    for _ in range(n_restarts):
        order = list(range(n))
        rng.shuffle(order)
        available = set(range(n))
        size = 0
        for v in order:
            if v in available:
                size += 1
                available -= nbr_sets[v]
                available.discard(v)
        best = max(best, size)

    return best


def compute_c_value(alpha, n, d_max):
    """Compute c = α·d_max / (N·log(d_max)).
    The conjecture states α(G) >= c·N·log(d)/d for some universal c > 0."""
    if d_max <= 1:
        return float("inf")
    return alpha * d_max / (n * math.log(d_max))


# ============================================================================
# Worker function for parallel execution
# ============================================================================

def evaluate_graph(spec):
    """Build one graph, compute all scores. Returns results dict.
    Designed to be called via ProcessPoolExecutor."""
    n = spec["n"]
    method = spec["method"]
    seed = spec["seed"]
    graph_id = spec["graph_id"]
    sat_timeout = spec.get("sat_timeout", 300)

    # Build graph
    build_t0 = time.time()
    if method in ("degree", "inverse_degree", "random", "balanced"):
        g = build_vertex_by_vertex(n, method, seed)
    elif method == "random_edge":
        g = build_random_edge(n, seed)
    elif method == "random_edge_capped":
        cap = int(math.sqrt(n * math.log(n)))
        g = build_random_edge(n, seed, degree_cap=cap)
    else:
        raise ValueError(f"Unknown method: {method}")
    build_time = time.time() - build_t0

    d_max = g.max_degree()

    # K4-freeness sanity check
    k4_free = verify_k4_free(g.adj)

    # Proxy scores
    cw = caro_wei_bound(g)
    gmis = greedy_mis(g.adj, n_restarts=20, seed=seed + 1000)

    # Exact alpha via SAT
    alpha, sat_time, sat_timed_out = alpha_sat(g.adj, timeout=sat_timeout)

    # c-values
    c_val = compute_c_value(alpha, n, d_max) if alpha > 0 and not sat_timed_out else None
    c_cw = compute_c_value(cw, n, d_max)
    c_greedy = compute_c_value(gmis, n, d_max)

    return {
        "graph_id": graph_id,
        "n": n,
        "method": method,
        "seed": seed,
        "num_edges": g.num_edges,
        "d_max": d_max,
        "k4_free": k4_free,
        "alpha_sat": alpha if not sat_timed_out else None,
        "sat_time_s": round(sat_time, 3),
        "sat_timed_out": sat_timed_out,
        "build_time_s": round(build_time, 3),
        "caro_wei": round(cw, 4),
        "greedy_mis": gmis,
        "c_value": round(c_val, 6) if c_val is not None else None,
        "c_caro_wei": round(c_cw, 6) if c_cw is not None and c_cw != float("inf") else None,
        "c_greedy": round(c_greedy, 6) if c_greedy is not None and c_greedy != float("inf") else None,
    }


# ============================================================================
# Analysis
# ============================================================================

def analyze_results(results):
    """Compute correlations, c-value stats, timing stats."""
    df = pd.DataFrame(results)

    # Filter to graphs with successful SAT
    df_sat = df[df["alpha_sat"].notna()].copy()

    summary = {
        "total_graphs": len(df),
        "k4_free_count": int(df["k4_free"].sum()),
        "k4_violation_count": int((~df["k4_free"]).sum()),
        "sat_success_count": len(df_sat),
        "sat_timeout_count": int(df["sat_timed_out"].sum()),
    }

    # Spearman correlations (overall and per-N)
    correlations = {}
    if len(df_sat) >= 5:
        for proxy_col, proxy_name in [("caro_wei", "caro_wei"), ("greedy_mis", "greedy_mis")]:
            rho, pval = spearmanr(df_sat[proxy_col], df_sat["alpha_sat"])
            correlations[f"{proxy_name}_vs_alpha_overall"] = {
                "rho": round(float(rho), 4),
                "p_value": round(float(pval), 6),
                "n_samples": len(df_sat),
            }

        # Per-N correlations
        for n_val in sorted(df_sat["n"].unique()):
            sub = df_sat[df_sat["n"] == n_val]
            if len(sub) >= 5:
                for proxy_col, proxy_name in [("caro_wei", "caro_wei"), ("greedy_mis", "greedy_mis")]:
                    rho, pval = spearmanr(sub[proxy_col], sub["alpha_sat"])
                    correlations[f"{proxy_name}_vs_alpha_N{n_val}"] = {
                        "rho": round(float(rho), 4),
                        "p_value": round(float(pval), 6),
                        "n_samples": len(sub),
                    }

    summary["correlations"] = correlations

    # c-value stats by method and N
    c_stats = {}
    for method in df_sat["method"].unique():
        c_stats[method] = {}
        for n_val in sorted(df_sat["n"].unique()):
            sub = df_sat[(df_sat["method"] == method) & (df_sat["n"] == n_val)]
            if len(sub) > 0 and sub["c_value"].notna().any():
                vals = sub["c_value"].dropna()
                c_stats[method][f"N={n_val}"] = {
                    "count": len(vals),
                    "mean": round(float(vals.mean()), 4),
                    "min": round(float(vals.min()), 4),
                    "max": round(float(vals.max()), 4),
                    "std": round(float(vals.std()), 4) if len(vals) > 1 else 0,
                }
    summary["c_values_by_method"] = c_stats

    # SAT timing stats per N
    timing = {}
    for n_val in sorted(df["n"].unique()):
        sub = df[df["n"] == n_val]
        sat_times = sub["sat_time_s"]
        timing[f"N={n_val}"] = {
            "mean_s": round(float(sat_times.mean()), 2),
            "median_s": round(float(sat_times.median()), 2),
            "max_s": round(float(sat_times.max()), 2),
            "timeout_count": int(sub["sat_timed_out"].sum()),
            "total_graphs": len(sub),
        }
    summary["sat_timing"] = timing

    return df, summary


def print_summary(summary):
    """Print formatted summary to console."""
    print("\n" + "=" * 60)
    print("VALIDATION EXPERIMENT RESULTS")
    print("=" * 60)

    print(f"\nTotal graphs:       {summary['total_graphs']}")
    print(f"K4-free:            {summary['k4_free_count']}")
    if summary["k4_violation_count"] > 0:
        print(f"K4 VIOLATIONS:      {summary['k4_violation_count']}  *** BUG ***")
    print(f"SAT solved:         {summary['sat_success_count']}")
    print(f"SAT timeouts:       {summary['sat_timeout_count']}")

    print("\n--- Proxy vs True Alpha Correlations ---")
    for key, val in summary.get("correlations", {}).items():
        print(f"  {key}: rho={val['rho']:.4f}  p={val['p_value']:.4e}  (n={val['n_samples']})")

    print("\n--- c-value Statistics by Method ---")
    for method, by_n in summary.get("c_values_by_method", {}).items():
        for nkey, stats in by_n.items():
            print(f"  {method:20s} {nkey}: mean={stats['mean']:.4f}  "
                  f"min={stats['min']:.4f}  max={stats['max']:.4f}  "
                  f"std={stats['std']:.4f}  (n={stats['count']})")

    print("\n--- SAT Timing ---")
    for nkey, stats in summary.get("sat_timing", {}).items():
        print(f"  {nkey}: mean={stats['mean_s']:.1f}s  median={stats['median_s']:.1f}s  "
              f"max={stats['max_s']:.1f}s  timeouts={stats['timeout_count']}/{stats['total_graphs']}")

    print("=" * 60)


def generate_plots(df, outdir):
    """Generate scatter plots of proxy vs true alpha and c vs N."""
    plots_dir = os.path.join(outdir, "plots")
    os.makedirs(plots_dir, exist_ok=True)

    df_sat = df[df["alpha_sat"].notna()].copy()
    if len(df_sat) < 2:
        print("Not enough data for plots.")
        return

    # Plot 1: Caro-Wei vs true alpha
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    ax = axes[0]
    for n_val in sorted(df_sat["n"].unique()):
        sub = df_sat[df_sat["n"] == n_val]
        ax.scatter(sub["alpha_sat"], sub["caro_wei"], label=f"N={n_val}", alpha=0.7, s=30)
    ax.set_xlabel("True α (SAT)")
    ax.set_ylabel("Caro-Wei bound")
    ax.set_title("Caro-Wei vs True α")
    ax.legend()
    # Reference line y=x
    lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]), max(ax.get_xlim()[1], ax.get_ylim()[1])]
    ax.plot(lims, lims, "k--", alpha=0.3, label="y=x")
    ax.grid(True, alpha=0.3)

    # Plot 2: Greedy MIS vs true alpha
    ax = axes[1]
    for n_val in sorted(df_sat["n"].unique()):
        sub = df_sat[df_sat["n"] == n_val]
        ax.scatter(sub["alpha_sat"], sub["greedy_mis"], label=f"N={n_val}", alpha=0.7, s=30)
    ax.set_xlabel("True α (SAT)")
    ax.set_ylabel("Greedy MIS")
    ax.set_title("Greedy MIS vs True α")
    ax.legend()
    lims = [min(ax.get_xlim()[0], ax.get_ylim()[0]), max(ax.get_xlim()[1], ax.get_ylim()[1])]
    ax.plot(lims, lims, "k--", alpha=0.3, label="y=x")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "proxy_vs_alpha.png"), dpi=150)
    plt.close()

    # Plot 3: c-value by method and N
    fig, ax = plt.subplots(figsize=(10, 6))
    methods = sorted(df_sat["method"].unique())
    n_vals = sorted(df_sat["n"].unique())
    width = 0.12
    x = np.arange(len(n_vals))

    for i, method in enumerate(methods):
        means = []
        stds = []
        for n_val in n_vals:
            sub = df_sat[(df_sat["method"] == method) & (df_sat["n"] == n_val)]
            vals = sub["c_value"].dropna()
            means.append(float(vals.mean()) if len(vals) > 0 else 0)
            stds.append(float(vals.std()) if len(vals) > 1 else 0)
        ax.bar(x + i * width, means, width, yerr=stds, label=method, alpha=0.8, capsize=3)

    ax.set_xlabel("N")
    ax.set_ylabel("c = α·d_max / (N·log(d_max))")
    ax.set_title("c-value by Construction Method")
    ax.set_xticks(x + width * (len(methods) - 1) / 2)
    ax.set_xticklabels([str(n) for n in n_vals])
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, "c_value_by_method.png"), dpi=150)
    plt.close()

    print(f"Plots saved to {plots_dir}/")


# ============================================================================
# Invariant checks
# ============================================================================

def check_invariants(results):
    """Validate expected invariants on results."""
    violations = []
    for r in results:
        gid = r["graph_id"]

        if not r["k4_free"]:
            violations.append(f"Graph {gid}: K4 violation!")

        if r["alpha_sat"] is not None:
            if r["greedy_mis"] > r["alpha_sat"]:
                violations.append(
                    f"Graph {gid}: greedy_mis ({r['greedy_mis']}) > "
                    f"alpha_sat ({r['alpha_sat']})")

            if r["caro_wei"] > r["alpha_sat"] + 0.01:
                violations.append(
                    f"Graph {gid}: caro_wei ({r['caro_wei']:.2f}) > "
                    f"alpha_sat ({r['alpha_sat']}) — Caro-Wei lower bound violated")

    if violations:
        print("\n*** INVARIANT VIOLATIONS ***")
        for v in violations:
            print(f"  {v}")
        print()
    else:
        print("\nAll invariants passed.")

    return violations


# ============================================================================
# Main
# ============================================================================

ALL_METHODS = ["degree", "inverse_degree", "random", "balanced",
               "random_edge", "random_edge_capped"]


def main():
    parser = argparse.ArgumentParser(
        description="K4-free independence number validation experiment")
    parser.add_argument("--sizes", nargs="+", type=int, default=[40, 60, 80],
                        help="Graph sizes N (default: 40 60 80)")
    parser.add_argument("--methods", nargs="+", default=ALL_METHODS,
                        help=f"Construction methods (default: {ALL_METHODS})")
    parser.add_argument("--graphs-per-config", type=int, default=10,
                        help="Graphs per (N, method) configuration (default: 10)")
    parser.add_argument("--outdir", default="results",
                        help="Output directory (default: results)")
    parser.add_argument("--workers", type=int, default=None,
                        help="Parallel workers (default: cpu_count // 2)")
    parser.add_argument("--sat-timeout", type=float, default=300,
                        help="SAT timeout per graph in seconds (default: 300)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Base random seed (default: 42)")
    parser.add_argument("--quick", action="store_true",
                        help="Quick smoke test: N=12, 2 graphs per config")
    args = parser.parse_args()

    if args.quick:
        args.sizes = [12]
        args.graphs_per_config = 2
        args.sat_timeout = 30

    # Generate graph specs
    specs = []
    graph_id = 0
    for n in args.sizes:
        for method in args.methods:
            for trial in range(args.graphs_per_config):
                specs.append({
                    "graph_id": graph_id,
                    "n": n,
                    "method": method,
                    "seed": args.seed + graph_id * 7919,  # spread seeds
                    "sat_timeout": args.sat_timeout,
                })
                graph_id += 1

    total = len(specs)
    workers = args.workers or max(1, os.cpu_count() // 2)

    print(f"K4-Free Validation Experiment")
    print(f"  Sizes: {args.sizes}")
    print(f"  Methods: {args.methods}")
    print(f"  Graphs per config: {args.graphs_per_config}")
    print(f"  Total graphs: {total}")
    print(f"  Workers: {workers}")
    print(f"  SAT timeout: {args.sat_timeout}s")
    print(f"  Output: {args.outdir}/")
    print()

    # Run evaluations in parallel
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(evaluate_graph, spec): spec for spec in specs}
        with tqdm(total=total, desc="Evaluating graphs") as pbar:
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    spec = futures[future]
                    print(f"\nERROR on graph {spec['graph_id']} "
                          f"(n={spec['n']}, {spec['method']}): {e}")
                    results.append({
                        "graph_id": spec["graph_id"],
                        "n": spec["n"],
                        "method": spec["method"],
                        "seed": spec["seed"],
                        "error": str(e),
                    })
                pbar.update(1)

    # Sort by graph_id for consistent output
    results.sort(key=lambda r: r.get("graph_id", 0))

    # Check invariants
    check_invariants([r for r in results if "error" not in r])

    # Analyze
    df, summary = analyze_results([r for r in results if "error" not in r])

    # Print summary
    print_summary(summary)

    # Save outputs
    outdir = args.outdir
    os.makedirs(outdir, exist_ok=True)

    with open(os.path.join(outdir, "results.json"), "w") as f:
        json.dump(results, f, indent=2)

    with open(os.path.join(outdir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nResults written to {outdir}/results.json")
    print(f"Summary written to {outdir}/summary.json")

    # Generate plots
    generate_plots(df, outdir)


if __name__ == "__main__":
    main()
