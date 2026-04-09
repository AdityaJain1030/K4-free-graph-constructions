"""Pareto frontier scanner using CP-SAT ILP solver."""

import json
import sys
from math import log

import numpy as np

from k4free_ilp.ilp_solver import solve_k4free
from k4free_ilp.alpha_exact import alpha_exact
from k4free_ilp.graph_io import adj_to_g6, adj_to_edge_list


def scan_pareto_frontier(n: int, time_limit_per_query: int = 300) -> list[dict]:
    """
    Find Pareto-optimal (α, d_max) pairs for K₄-free graphs on n vertices.

    Uses binary search: for each candidate α value k (from 1 upward),
    find the minimum d_max D such that a K₄-free graph with α ≤ k
    and d_max ≤ D exists.

    Returns list of dicts with keys: alpha, d_max, c_log, edges, g6, solve_time, status
    """
    achievable = []  # list of (alpha, d_max, adj, total_solve_time)

    for k in range(1, n):
        # Binary search for minimum D
        lo, hi = 1, n - 1
        best_D = None
        best_adj = None
        total_time = 0.0

        # First check if ANY D works (test D = n-1)
        status, adj, stats = solve_k4free(n, k, n - 1, time_limit_per_query)
        total_time += stats["solve_time"]
        print(f"  n={n}, testing α≤{k}, D≤{n-1}... {status} ({stats['solve_time']:.1f}s)",
              flush=True)

        if status == "INFEASIBLE":
            # α ≤ k is impossible for any degree — stop, larger k trivially achievable
            # Actually, if α ≤ k is infeasible even with max degree, it means we need MORE edges
            # but that's contradictory. This means k is too small.
            # Continue to next k.
            continue
        elif status == "TIMEOUT":
            continue

        # Feasible at D = n-1. Binary search for minimum D.
        best_D = n - 1
        best_adj = adj

        while lo < hi:
            mid = (lo + hi) // 2
            status, adj, stats = solve_k4free(n, k, mid, time_limit_per_query)
            total_time += stats["solve_time"]
            print(f"  n={n}, testing α≤{k}, D≤{mid}... {status} ({stats['solve_time']:.1f}s)",
                  flush=True)

            if status == "FEASIBLE":
                hi = mid
                best_D = mid
                best_adj = adj
            else:
                lo = mid + 1

        # Verify lo if we haven't tested it directly
        if lo == hi and lo < best_D:
            status, adj, stats = solve_k4free(n, k, lo, time_limit_per_query)
            total_time += stats["solve_time"]
            print(f"  n={n}, testing α≤{k}, D≤{lo}... {status} ({stats['solve_time']:.1f}s)",
                  flush=True)
            if status == "FEASIBLE":
                best_D = lo
                best_adj = adj

        if best_adj is not None:
            achievable.append((k, best_D, best_adj, total_time))

    # Add trivial points that the binary search (D≥1, k<n) misses:
    # Empty graph: α=n, d_max=0
    empty_adj = np.zeros((n, n), dtype=np.uint8)
    achievable.append((n, 0, empty_adj, 0.0))

    # Perfect/near-perfect matching: α = ceil(n/2), d_max = 1 if n ≥ 2
    if n >= 2:
        match_adj = np.zeros((n, n), dtype=np.uint8)
        for i in range(0, n - 1, 2):
            match_adj[i, i + 1] = match_adj[i + 1, i] = 1
        match_alpha = (n + 1) // 2  # ceil(n/2)
        achievable.append((match_alpha, 1, match_adj, 0.0))

    # Extract Pareto frontier from achievable points
    # We want to minimize both α and d_max
    points = [(a, d, adj, t) for a, d, adj, t in achievable]
    pareto = []
    for i, (a, d, adj, t) in enumerate(points):
        dominated = False
        for j, (a2, d2, _, _) in enumerate(points):
            if i == j:
                continue
            if a2 <= a and d2 <= d and (a2 < a or d2 < d):
                dominated = True
                break
        if not dominated:
            pareto.append((a, d, adj, t))

    pareto.sort(key=lambda x: (x[0], x[1]))

    result = []
    for alpha, d_max, adj, solve_time in pareto:
        edges = adj_to_edge_list(adj)
        g6 = adj_to_g6(adj)
        c_log = None
        if d_max > 1:
            c_log = round(alpha * d_max / (n * log(d_max)), 4)
        result.append({
            "alpha": int(alpha),
            "d_max": int(d_max),
            "c_log": c_log,
            "edges": edges,
            "g6": g6,
            "solve_time": round(solve_time, 3),
            "status": "FEASIBLE",
        })

    return result


def main():
    results_dir = "k4free_ilp/results"
    summary_rows = []

    n_values = range(4, 16) if len(sys.argv) < 2 else [int(x) for x in sys.argv[1:]]

    for n in n_values:
        print(f"\n=== n={n} ===", flush=True)
        pareto = scan_pareto_frontier(n, time_limit_per_query=300)

        c_values = [p["c_log"] for p in pareto if p["c_log"] is not None]
        min_c = min(c_values) if c_values else None

        best_point = None
        if min_c is not None:
            for p in pareto:
                if p["c_log"] == min_c:
                    best_point = p
                    break

        result = {
            "n": n,
            "pareto_frontier": pareto,
            "min_c_log": min_c,
        }

        path = f"{results_dir}/ilp_pareto_n{n}.json"
        with open(path, 'w') as f:
            json.dump(result, f, indent=2)

        summary_rows.append({
            "n": n,
            "best_alpha": best_point["alpha"] if best_point else "-",
            "best_d": best_point["d_max"] if best_point else "-",
            "min_c_log": min_c if min_c is not None else "-",
            "witness_edges": len(best_point["edges"]) if best_point else "-",
            "pareto_points": len(pareto),
        })

    print()
    print(f"{'n':>3} | {'best_α':>6} | {'best_d':>6} | {'min_c_log':>10} | {'witness_edges':>13} | {'pareto_pts':>10}")
    print("-" * 65)
    for r in summary_rows:
        print(f"{r['n']:>3} | {r['best_alpha']:>6} | {r['best_d']:>6} | {str(r['min_c_log']):>10} | {str(r['witness_edges']):>13} | {r['pareto_points']:>10}")


if __name__ == "__main__":
    main()
