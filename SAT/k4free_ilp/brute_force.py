"""Compute exact Pareto frontiers for K₄-free graphs, n=3..10."""

import json
import subprocess
import sys
from math import log
import numpy as np
import networkx as nx

from k4free_ilp.k4_check import is_k4_free
from k4free_ilp.alpha_exact import alpha_exact
from k4free_ilp.graph_io import adj_to_g6, adj_to_edge_list


def compute_d_max(adj: np.ndarray) -> int:
    """Maximum degree of the graph."""
    return int(adj.sum(axis=1).max())


def enumerate_all_edge_bitmasks(n: int):
    """Enumerate all graphs on n vertices by iterating over edge bitmasks."""
    # Number of possible edges
    num_edges = n * (n - 1) // 2
    # Build edge index: map bit position -> (i, j)
    edge_list = []
    for i in range(n):
        for j in range(i + 1, n):
            edge_list.append((i, j))

    for mask in range(1 << num_edges):
        adj = np.zeros((n, n), dtype=np.uint8)
        for bit, (i, j) in enumerate(edge_list):
            if mask >> bit & 1:
                adj[i, j] = adj[j, i] = 1
        yield adj


def enumerate_geng(n: int):
    """Enumerate all non-isomorphic graphs on n vertices using nauty's geng."""
    proc = subprocess.Popen(
        ['geng', '-q', str(n)],
        stdout=subprocess.PIPE,
    )
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        G = nx.from_graph6_bytes(line)
        while G.number_of_nodes() < n:
            G.add_node(G.number_of_nodes())
        adj = nx.to_numpy_array(G, dtype=np.uint8)
        yield adj
    proc.wait()


def compute_pareto_frontier(n: int, use_geng: bool = False):
    """Compute K₄-free Pareto frontier for given n.

    Returns (pareto_points, total_k4free) where pareto_points is list of dicts.
    """
    # Collect all (alpha, d_max) pairs with witness graphs
    # Key: (alpha, d_max) -> adj matrix (keep first witness)
    achieved = {}
    total_k4free = 0

    if use_geng:
        graph_iter = enumerate_geng(n)
    else:
        graph_iter = enumerate_all_edge_bitmasks(n)

    count = 0
    for adj in graph_iter:
        count += 1
        if count % 500000 == 0:
            print(f"    processed {count} graphs, {total_k4free} K4-free so far...", flush=True)
        if not is_k4_free(adj):
            continue
        total_k4free += 1
        alpha, _ = alpha_exact(adj)
        d_max = compute_d_max(adj)
        key = (alpha, d_max)
        if key not in achieved:
            achieved[key] = adj.copy()

    # Compute Pareto frontier: (alpha, d_max) is Pareto-optimal if
    # no other point has alpha' <= alpha AND d' <= d with at least one strict
    # i.e., we want to MINIMIZE both alpha and d_max
    points = list(achieved.keys())
    pareto = []
    for (a, d) in points:
        dominated = False
        for (a2, d2) in points:
            if (a2, d2) == (a, d):
                continue
            if a2 <= a and d2 <= d:
                dominated = True
                break
        if not dominated:
            pareto.append((a, d))

    pareto.sort(key=lambda x: (x[0], x[1]))

    # Build result
    pareto_points = []
    for (alpha, d_max) in pareto:
        adj = achieved[(alpha, d_max)]
        edges = adj_to_edge_list(adj)
        g6 = adj_to_g6(adj)
        c_log = None
        if d_max > 1:
            c_log = round(alpha * d_max / (n * log(d_max)), 4)
        pareto_points.append({
            "alpha": int(alpha),
            "d_max": int(d_max),
            "c_log": c_log,
            "edges": edges,
            "g6": g6,
        })

    return pareto_points, total_k4free


def main():
    results_dir = "k4free_ilp/results"
    summary_rows = []

    for n in range(3, 11):
        use_geng = n >= 8
        print(f"n={n} ({'geng' if use_geng else 'brute force'})...", flush=True)
        pareto_points, total_k4free = compute_pareto_frontier(n, use_geng=use_geng)

        # Find min c_log
        c_values = [p["c_log"] for p in pareto_points if p["c_log"] is not None]
        min_c = min(c_values) if c_values else None

        # Find best witness (min c_log)
        best_point = None
        if min_c is not None:
            for p in pareto_points:
                if p["c_log"] == min_c:
                    best_point = p
                    break

        result = {
            "n": n,
            "pareto_frontier": pareto_points,
            "min_c_log": min_c,
            "total_k4free_graphs": total_k4free,
        }

        path = f"{results_dir}/brute_force_n{n}.json"
        with open(path, 'w') as f:
            json.dump(result, f, indent=2)
        print(f"  -> {len(pareto_points)} Pareto points, {total_k4free} K4-free graphs, min_c_log={min_c}")

        summary_rows.append({
            "n": n,
            "best_alpha": best_point["alpha"] if best_point else "-",
            "best_d": best_point["d_max"] if best_point else "-",
            "min_c_log": min_c if min_c is not None else "-",
            "witness_edges": len(best_point["edges"]) if best_point else "-",
            "total_k4free": total_k4free,
        })

    # Print summary table
    print()
    print(f"{'n':>3} | {'best_α':>6} | {'best_d':>6} | {'min_c_log':>10} | {'witness_edges':>13} | {'total_K4free':>12}")
    print("-" * 65)
    for r in summary_rows:
        print(f"{r['n']:>3} | {r['best_alpha']:>6} | {r['best_d']:>6} | {str(r['min_c_log']):>10} | {str(r['witness_edges']):>13} | {r['total_k4free']:>12}")


if __name__ == "__main__":
    main()
