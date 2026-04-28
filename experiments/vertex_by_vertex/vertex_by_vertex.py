#!/usr/bin/env python3
"""
experiments/vertex_by_vertex/vertex_by_vertex.py
=================================================
Quantifies the degree-gradient failure mode of vertex-by-vertex K₄-free graph
construction. Builds graphs by adding one vertex at a time with four priority
functions, records c_log and degree-sequence statistics, and plots the results.

The main finding: all vertex-by-vertex methods produce c_log ≫ 1 due to a
structural degree imbalance — early vertices accumulate edges from all later
vertices, inflating d_max and thus c_log. The random-edge-with-degree-cap
baseline is included as a comparison. See README.md for full context.

Usage
-----
    micromamba run -n k4free python experiments/vertex_by_vertex/vertex_by_vertex.py
    micromamba run -n k4free python experiments/vertex_by_vertex/vertex_by_vertex.py --quick
    micromamba run -n k4free python experiments/vertex_by_vertex/vertex_by_vertex.py \\
        --sizes 20 40 60 --methods high_degree random --graphs-per-config 20
"""

from __future__ import annotations

import argparse
import csv
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

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from utils.graph_props import alpha_bb_clique_cover

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")

# ---------------------------------------------------------------------------
# K₄-free graph builder
# ---------------------------------------------------------------------------

def would_create_k4(adj: list[set], u: int, v: int) -> bool:
    """Return True if adding edge (u, v) creates a K₄."""
    common = adj[u] & adj[v]
    for w in common:
        if adj[u] & adj[v] & adj[w]:
            return True
    return False


def build_vertex_by_vertex(n: int, method: str, rng: random.Random) -> list[set]:
    """
    Add vertices 0..n-1 one at a time. For each new vertex v, attempt to wire
    it to existing vertices in an order determined by `method`, skipping edges
    that would create a K₄.

    Returns adjacency list (list of sets).
    """
    adj: list[set] = [set() for _ in range(n)]
    degree = [0] * n

    for v in range(1, n):
        candidates = list(range(v))

        if method == "high_degree":
            candidates.sort(key=lambda u: -degree[u])
        elif method == "low_degree":
            candidates.sort(key=lambda u: degree[u])
        elif method == "random":
            rng.shuffle(candidates)
        elif method == "max_neighbors":
            # Prefer vertices that share the most neighbors with v's current
            # neighborhood (maximises triangle density around v).
            candidates.sort(key=lambda u: -len(adj[v] & adj[u]))
        else:
            raise ValueError(f"Unknown method: {method}")

        for u in candidates:
            if not would_create_k4(adj, u, v):
                adj[u].add(v)
                adj[v].add(u)
                degree[u] += 1
                degree[v] += 1

    return adj


# ---------------------------------------------------------------------------
# Graph metrics
# ---------------------------------------------------------------------------

def adj_to_edge_list(adj: list[set]) -> list[tuple[int, int]]:
    edges = []
    for u, nbrs in enumerate(adj):
        for v in nbrs:
            if v > u:
                edges.append((u, v))
    return edges


def c_log(n: int, alpha: int, d_max: int) -> float:
    if d_max <= 1:
        return float("inf")
    return alpha * d_max / (n * math.log(d_max))


def gini(values: list[int]) -> float:
    if not values or max(values) == 0:
        return 0.0
    arr = sorted(values)
    n = len(arr)
    cumsum = 0.0
    for i, v in enumerate(arr):
        cumsum += (2 * (i + 1) - n - 1) * v
    return cumsum / (n * sum(arr))


def graph_stats(adj: list[set]) -> dict:
    n = len(adj)
    degrees = [len(nbrs) for nbrs in adj]
    d_max = max(degrees) if degrees else 0
    d_mean = sum(degrees) / n if n else 0
    d_std = (sum((d - d_mean) ** 2 for d in degrees) / n) ** 0.5 if n else 0

    edges = adj_to_edge_list(adj)
    adj_matrix = np.zeros((n, n), dtype=np.bool_)
    for u, v in edges:
        adj_matrix[u, v] = True
        adj_matrix[v, u] = True
    alpha, _ = alpha_bb_clique_cover(adj_matrix)

    return {
        "n": n,
        "num_edges": len(edges),
        "d_max": d_max,
        "d_mean": round(d_mean, 3),
        "d_std": round(d_std, 3),
        "d_gini": round(gini(degrees), 4),
        "alpha": alpha,
        "c_log": round(c_log(n, alpha, d_max), 4) if d_max > 1 else None,
    }


# ---------------------------------------------------------------------------
# Baseline: random edge addition with degree cap
# ---------------------------------------------------------------------------

def build_random_edge_capped(n: int, rng: random.Random) -> list[set]:
    """
    Random-edge-with-degree-cap baseline from funsearch Experiment 1.
    Attempts random edges until no valid edge remains; degree cap = sqrt(N log N).
    """
    cap = max(2, int(math.sqrt(n * math.log(max(n, 2)))))
    adj: list[set] = [set() for _ in range(n)]
    degree = [0] * n

    all_pairs = [(u, v) for u in range(n) for v in range(u + 1, n)]
    rng.shuffle(all_pairs)

    for u, v in all_pairs:
        if degree[u] >= cap or degree[v] >= cap:
            continue
        if not would_create_k4(adj, u, v):
            adj[u].add(v)
            adj[v].add(u)
            degree[u] += 1
            degree[v] += 1

    return adj


# ---------------------------------------------------------------------------
# Experiment runner
# ---------------------------------------------------------------------------

METHODS = ["high_degree", "low_degree", "random", "max_neighbors"]


def run_experiment(
    sizes: list[int],
    methods: list[str],
    graphs_per_config: int,
    base_seed: int,
) -> list[dict]:
    rows = []
    total = len(sizes) * (len(methods) + 1) * graphs_per_config
    done = 0

    for n in sizes:
        for method in methods + ["random_edge_capped"]:
            for i in range(graphs_per_config):
                seed = base_seed + n * 10000 + hash(method) % 10000 + i
                rng = random.Random(seed)

                t0 = time.perf_counter()
                if method == "random_edge_capped":
                    adj = build_random_edge_capped(n, rng)
                else:
                    adj = build_vertex_by_vertex(n, method, rng)
                build_time = time.perf_counter() - t0

                stats = graph_stats(adj)
                row = {"method": method, "seed": seed, "build_time_s": round(build_time, 4), **stats}
                rows.append(row)

                done += 1
                print(f"  [{done}/{total}] n={n} method={method} seed={i} "
                      f"c_log={row['c_log']}  d_max={row['d_max']}  α={row['alpha']}")

    return rows


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def plot_c_log_by_method(rows: list[dict], outdir: str) -> None:
    methods = sorted(set(r["method"] for r in rows))
    sizes = sorted(set(r["n"] for r in rows))

    fig, ax = plt.subplots(figsize=(9, 5))
    markers = ["o", "s", "^", "D", "x"]

    for i, method in enumerate(methods):
        xs, ys, errs = [], [], []
        for n in sizes:
            vals = [r["c_log"] for r in rows if r["method"] == method and r["n"] == n and r["c_log"] is not None]
            if vals:
                xs.append(n)
                ys.append(np.mean(vals))
                errs.append(np.std(vals))
        ax.errorbar(xs, ys, yerr=errs, label=method, marker=markers[i % len(markers)], capsize=3)

    ax.axhline(0.679, color="red", linestyle="--", linewidth=1.2, label="P(17) benchmark (0.679)")
    ax.axhline(1.0, color="grey", linestyle=":", linewidth=0.8)
    ax.set_xlabel("N")
    ax.set_ylabel("c_log  (lower is better)")
    ax.set_title("c_log vs N — vertex-by-vertex vs random-edge baseline")
    ax.legend(fontsize=8)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    path = os.path.join(outdir, "c_log_by_method.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved {path}")


def plot_degree_skew(rows: list[dict], outdir: str) -> None:
    fig, ax = plt.subplots(figsize=(7, 5))
    methods = sorted(set(r["method"] for r in rows))
    colors = plt.cm.tab10.colors

    for i, method in enumerate(methods):
        sub = [r for r in rows if r["method"] == method and r["c_log"] is not None]
        if not sub:
            continue
        ax.scatter(
            [r["d_gini"] for r in sub],
            [r["c_log"] for r in sub],
            label=method, alpha=0.6, s=20, color=colors[i % len(colors)],
        )

    ax.axhline(0.679, color="red", linestyle="--", linewidth=1.0, label="P(17) benchmark")
    ax.set_xlabel("Degree Gini coefficient  (0 = uniform, 1 = maximally skewed)")
    ax.set_ylabel("c_log")
    ax.set_title("Degree skew vs c_log")
    ax.legend(fontsize=8)
    fig.tight_layout()
    path = os.path.join(outdir, "degree_skew_vs_c.png")
    fig.savefig(path, dpi=150)
    plt.close(fig)
    print(f"Saved {path}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def summarise(rows: list[dict]) -> dict:
    from collections import defaultdict
    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r["method"], r["n"])].append(r)

    summary = {}
    for (method, n), group in sorted(groups.items()):
        clogs = [r["c_log"] for r in group if r["c_log"] is not None]
        summary[f"{method}_n{n}"] = {
            "method": method, "n": n, "count": len(group),
            "c_log_mean": round(float(np.mean(clogs)), 4) if clogs else None,
            "c_log_min":  round(float(np.min(clogs)), 4)  if clogs else None,
            "c_log_std":  round(float(np.std(clogs)), 4)  if clogs else None,
            "d_max_mean": round(float(np.mean([r["d_max"] for r in group])), 2),
            "d_gini_mean": round(float(np.mean([r["d_gini"] for r in group])), 4),
        }
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Vertex-by-vertex K₄-free construction experiment")
    parser.add_argument("--sizes", nargs="+", type=int, default=[10, 15, 20, 30, 40, 50])
    parser.add_argument("--methods", nargs="+", default=METHODS)
    parser.add_argument("--graphs-per-config", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--outdir", default=RESULTS_DIR)
    parser.add_argument("--quick", action="store_true", help="Smoke test: N=10..20, 3 graphs/config")
    args = parser.parse_args()

    if args.quick:
        args.sizes = [10, 15, 20]
        args.graphs_per_config = 3

    os.makedirs(args.outdir, exist_ok=True)

    print(f"Sizes: {args.sizes}")
    print(f"Methods: {args.methods} + random_edge_capped (baseline)")
    print(f"Graphs per config: {args.graphs_per_config}")
    print()

    rows = run_experiment(args.sizes, args.methods, args.graphs_per_config, args.seed)

    # Save CSV
    csv_path = os.path.join(args.outdir, "results.csv")
    fieldnames = ["method", "n", "seed", "num_edges", "d_max", "d_mean", "d_std",
                  "d_gini", "alpha", "c_log", "build_time_s"]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved {csv_path}")

    # Save summary JSON
    summary = summarise(rows)
    summary_path = os.path.join(args.outdir, "summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Saved {summary_path}")

    # Plots
    plot_c_log_by_method(rows, args.outdir)
    plot_degree_skew(rows, args.outdir)

    # Print headline numbers
    print("\n--- Headline results ---")
    print(f"{'Method':<22} {'N':>4}  {'c_log mean':>10}  {'c_log min':>9}  {'gini':>6}")
    print("-" * 60)
    for key, s in summary.items():
        print(f"{s['method']:<22} {s['n']:>4}  {s['c_log_mean']:>10}  {s['c_log_min']:>9}  {s['d_gini_mean']:>6}")


if __name__ == "__main__":
    main()
