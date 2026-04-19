"""CLI and output formatting for the minimum-edge K₄-free solver.

Two modes:
  single: solve one (n, max_alpha) instance
  scan:   sweep n_min..n_max at Ramsey-floor α
"""

import argparse
import json
import os
import sys
import time
from math import log, ceil

import numpy as np

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from regular_sat.solver import solve_min_edges
from regular_sat.graph_io import adj_to_g6, adj_to_edge_list

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")


# ---------------------------------------------------------------------------
# Ramsey-floor lookup
# ---------------------------------------------------------------------------

def ramsey_floor_alpha(n: int) -> int:
    """Return the Ramsey-floor max_alpha for a given n.

    This is the largest α such that R(4, α) ≤ n, i.e. there exist K₄-free
    graphs on n vertices with independence number ≤ α.
    """
    # R(4,3)=9, R(4,4)=18, R(4,5)=25
    if 9 <= n <= 17:
        return 3
    elif 18 <= n <= 24:
        return 4
    elif 25 <= n <= 35:
        return 5
    else:
        raise ValueError(f"n={n} outside supported range [9, 35]")


# ---------------------------------------------------------------------------
# Derived fields
# ---------------------------------------------------------------------------

def enrich_result(result: dict, n: int, max_alpha: int) -> dict:
    """Add derived fields to raw solver output. Returns a new dict."""
    out = {
        "n": n,
        "max_alpha": max_alpha,
        "status": result["status"],
        "solve_time": result["solve_time"],
        "method": result["method"],
        "iterations": result["iterations"],
    }

    if result["adjacency"] is None:
        out.update({
            "num_edges": None, "alpha": None, "D": None,
            "d_min": None, "d_max": None, "d_avg": None,
            "c_log": None, "beta": None,
            "edges": None, "g6": None, "degree_sequence": None,
        })
        return out

    adj = np.array(result["adjacency"], dtype=np.uint8)
    degrees = adj.sum(axis=1).astype(int)
    d_min = int(degrees.min())
    d_max = int(degrees.max())
    d_avg = float(degrees.mean())
    alpha = result["alpha"]
    num_edges = result["num_edges"]

    # c_log: α * d_max / (n * ln(d_max))
    c_log = None
    if d_max > 1:
        c_log = round(alpha * d_max / (n * log(d_max)), 4)

    # beta: from d_avg = (n/α) * (ln(n/α))^β
    # => β = ln(d_avg * α / n) / ln(ln(n / α))
    beta = None
    if alpha is not None and alpha > 0 and n > alpha:
        ratio = n / alpha
        ln_ratio = log(ratio)
        if ln_ratio > 1 and d_avg * alpha / n > 0:
            numer = log(d_avg * alpha / n)
            denom = log(ln_ratio)
            if denom != 0:
                beta = round(numer / denom, 4)

    out.update({
        "num_edges": num_edges,
        "alpha": alpha,
        "D": result["D"],
        "d_min": d_min,
        "d_max": d_max,
        "d_avg": round(d_avg, 4),
        "c_log": c_log,
        "beta": beta,
        "degree_sequence": result["degree_sequence"],
        "edges": adj_to_edge_list(adj),
        "g6": result["g6"],
    })
    return out


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

def _save_json(data: dict, path: str):
    """Write JSON with sorted keys and 2-space indent."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Saved {path}")


def result_path(n: int, max_alpha: int) -> str:
    return os.path.join(RESULTS_DIR, f"n{n}_a{max_alpha}.json")


# ---------------------------------------------------------------------------
# CLI: single mode
# ---------------------------------------------------------------------------

def run_single(n: int, max_alpha: int = None, time_limit: int = 600,
               num_workers: int = None):
    if max_alpha is None:
        max_alpha = ramsey_floor_alpha(n)

    result = solve_min_edges(n, max_alpha, time_limit=time_limit,
                             num_workers=num_workers)
    enriched = enrich_result(result, n, max_alpha)

    # Print summary
    print(f"\n{'='*50}")
    print(f"n={n}, α≤{max_alpha}: {enriched['status']}")
    if enriched["num_edges"] is not None:
        print(f"  edges={enriched['num_edges']}, D={enriched['D']}, "
              f"d_min={enriched['d_min']}, d_max={enriched['d_max']}, "
              f"d_avg={enriched['d_avg']}")
        print(f"  alpha={enriched['alpha']}, c_log={enriched['c_log']}, "
              f"beta={enriched['beta']}")
        print(f"  g6={enriched['g6']}")
    print(f"  time={enriched['solve_time']}s, method={enriched['method']}, "
          f"iterations={enriched['iterations']}")

    # Save
    _save_json(enriched, result_path(n, max_alpha))
    return enriched


# ---------------------------------------------------------------------------
# CLI: scan mode
# ---------------------------------------------------------------------------

def run_scan(n_min: int, n_max: int, time_limit: int = 600,
             num_workers: int = None):
    wall_t0 = time.time()
    all_results = []

    for n in range(n_min, n_max + 1):
        try:
            max_alpha = ramsey_floor_alpha(n)
        except ValueError:
            print(f"\nSkipping n={n} (outside Ramsey range)")
            continue

        print(f"\n{'='*60}")
        print(f"n={n}, α≤{max_alpha}")
        print(f"{'='*60}")

        result = solve_min_edges(n, max_alpha, time_limit=time_limit,
                                 num_workers=num_workers)
        enriched = enrich_result(result, n, max_alpha)
        all_results.append(enriched)

        # Save individual result
        _save_json(enriched, result_path(n, max_alpha))

    wall_time = round(time.time() - wall_t0, 3)

    # Print summary table
    print(f"\n{'='*80}")
    print(f"{'n':>3} {'α':>2} {'status':>10} {'|E|':>5} {'D':>3} "
          f"{'d_min':>5} {'d_max':>5} {'d_avg':>6} {'c_log':>7} "
          f"{'beta':>7} {'time':>8}")
    print("-" * 80)
    for r in all_results:
        status = r["status"][:7]
        edges = r["num_edges"] if r["num_edges"] is not None else "-"
        D = r["D"] if r["D"] is not None else "-"
        d_min = r["d_min"] if r["d_min"] is not None else "-"
        d_max = r["d_max"] if r["d_max"] is not None else "-"
        d_avg = f"{r['d_avg']:.2f}" if r["d_avg"] is not None else "-"
        c_log = f"{r['c_log']:.4f}" if r["c_log"] is not None else "-"
        beta = f"{r['beta']:.4f}" if r["beta"] is not None else "-"
        t = f"{r['solve_time']:.1f}s"
        print(f"{r['n']:>3} {r['max_alpha']:>2} {status:>10} {edges:>5} "
              f"{D:>3} {d_min:>5} {d_max:>5} {d_avg:>6} {c_log:>7} "
              f"{beta:>7} {t:>8}")
    print(f"\nWall time: {wall_time:.1f}s")

    # Save scan summary
    summary = {
        "n_min": n_min,
        "n_max": n_max,
        "time_limit": time_limit,
        "wall_time": wall_time,
        "results": all_results,
    }
    _save_json(summary, os.path.join(RESULTS_DIR, "scan_summary.json"))

    return all_results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Minimum-edge K₄-free solver CLI")
    sub = parser.add_subparsers(dest="mode", required=True)

    # single mode
    p_single = sub.add_parser("single", help="Solve one instance")
    p_single.add_argument("--n", type=int, required=True)
    p_single.add_argument("--max_alpha", type=int, default=None,
                          help="Override max_alpha (default: Ramsey floor)")
    p_single.add_argument("--time_limit", type=int, default=600)
    p_single.add_argument("--workers", type=int, default=None)

    # scan mode
    p_scan = sub.add_parser("scan", help="Sweep n range at Ramsey-floor α")
    p_scan.add_argument("--n_min", type=int, default=9)
    p_scan.add_argument("--n_max", type=int, default=35)
    p_scan.add_argument("--time_limit", type=int, default=600)
    p_scan.add_argument("--workers", type=int, default=None)

    args = parser.parse_args()

    if args.mode == "single":
        run_single(args.n, args.max_alpha, args.time_limit, args.workers)
    elif args.mode == "scan":
        run_scan(args.n_min, args.n_max, args.time_limit, args.workers)


if __name__ == "__main__":
    main()
