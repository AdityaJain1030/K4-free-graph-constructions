"""Production Pareto frontier sweep for n=11..35.

Usage:
    python -m k4free_ilp.run_production                # run all n=11..35
    python -m k4free_ilp.run_production 20 25 30       # run specific n values
    python -m k4free_ilp.run_production --dry-run      # show search plan without solving
    python -m k4free_ilp.run_production --workers 4    # use 4 solver workers (default: 8)
    python -m k4free_ilp.run_production --timeout 900  # override per-query time limit (seconds)
    python -m k4free_ilp.run_production -v             # verbose logging (show timeouts vs infeasible)
    python -m k4free_ilp.run_production -vv            # extra verbose (log every binary search step)
"""

import argparse
import json
import os
import sys
import time
from math import log, ceil
from concurrent.futures import ProcessPoolExecutor, as_completed

import numpy as np

from k4free_ilp.ilp_solver import solve_k4free, KNOWN_RAMSEY
from k4free_ilp.alpha_exact import alpha_exact
from k4free_ilp.graph_io import adj_to_g6, adj_to_edge_list

RESULTS_DIR = "k4free_ilp/results"

# Configurable globally so child processes inherit it
_SOLVER_WORKERS = 8
_VERBOSITY = 0  # 0=default, 1=verbose, 2=extra verbose


# --- Search space pruning ---

def min_alpha_for_n(n: int) -> int:
    """Minimum feasible α for K₄-free graphs on n vertices, from Ramsey bounds."""
    r4 = [(2, 4), (3, 9), (4, 18), (5, 25), (6, 36)]
    min_a = 1
    for t, r in r4:
        if n >= r:
            min_a = t
    return min_a


def max_dmax_for_n(n: int) -> int:
    """Turán bound: max degree ≤ 2n/3 + 2."""
    return 2 * n // 3 + 2


_TIMEOUT_OVERRIDE = None  # Set via --timeout flag to override per-query time limit


def time_limit_for_n(n: int) -> int:
    """Group A (n ≤ 20): 300s. Group B (n > 20): 600s. Overridden by --timeout."""
    if _TIMEOUT_OVERRIDE is not None:
        return _TIMEOUT_OVERRIDE
    return 300 if n <= 20 else 600


# --- Optimized scanner ---

def _binary_search_min_d(n, k, lo, hi, time_limit):
    """Binary search for minimum D where (n, α≤k, d≤D) is feasible.

    Returns (best_D, best_adj, best_stats, timeouts_list, total_time).
    best_D is None if infeasible/timeout at all D values.
    """
    timeouts = []
    total_time = 0.0
    best_D = None
    best_adj = None
    best_stats = None

    def _log_query(label, k, d, status, solve_time, stats):
        """Log a query result based on verbosity level."""
        if _VERBOSITY >= 2:
            method = stats.get("method", "?")
            iters = stats.get("iterations", 0)
            print(f"    [{label}] α≤{k}, D≤{d}: {status} "
                  f"({solve_time:.1f}s, method={method}, iters={iters})", flush=True)
        elif _VERBOSITY >= 1 and status != "FEASIBLE":
            print(f"    [{label}] α≤{k}, D≤{d}: {status} ({solve_time:.1f}s)", flush=True)

    # First check feasibility at hi
    status, adj, stats = solve_k4free(n, k, hi, time_limit)
    total_time += stats["solve_time"]
    _log_query("ceiling", k, hi, status, stats["solve_time"], stats)

    if status == "INFEASIBLE":
        return None, None, None, timeouts, total_time
    elif status == "TIMEOUT":
        timeouts.append({"alpha": k, "d_max": hi, "time": stats["solve_time"]})
        return None, None, None, timeouts, total_time

    best_D = hi
    best_adj = adj
    best_stats = stats

    while lo < hi:
        mid = (lo + hi) // 2
        status, adj, stats = solve_k4free(n, k, mid, time_limit)
        total_time += stats["solve_time"]
        _log_query("bsearch", k, mid, status, stats["solve_time"], stats)

        if status == "FEASIBLE":
            hi = mid
            best_D = mid
            best_adj = adj
            best_stats = stats
        elif status == "TIMEOUT":
            timeouts.append({"alpha": k, "d_max": mid, "time": stats["solve_time"]})
            lo = mid + 1
        else:
            lo = mid + 1

    if lo == hi and lo < best_D:
        status, adj, stats = solve_k4free(n, k, lo, time_limit)
        total_time += stats["solve_time"]
        _log_query("bsearch", k, lo, status, stats["solve_time"], stats)
        if status == "FEASIBLE":
            best_D = lo
            best_adj = adj
            best_stats = stats
        elif status == "TIMEOUT":
            timeouts.append({"alpha": k, "d_max": lo, "time": stats["solve_time"]})

    return best_D, best_adj, best_stats, timeouts, total_time


def scan_pareto_frontier_production(n: int, time_limit: int) -> dict:
    """Scan Pareto frontier for n with optimized search.

    Key optimizations vs naive scan:
    1. Search α from large→small, using monotonicity to tighten binary search bounds.
       If α=k has min_D=d, then α=k-1 needs min_D ≥ d.
    2. Early termination: stop once α reaches ceil(n/2) since matching gives D=1.
    3. Skip α values that can't improve the Pareto frontier.
    """
    min_k = min_alpha_for_n(n)
    max_d_turan = max_dmax_for_n(n)
    matching_alpha = (n + 1) // 2  # ceil(n/2) — matching always achieves D=1

    timeouts = []
    achievable = []  # (alpha, d_max, adj, solve_time, method, iterations)
    total_time = 0.0

    # Search from large α downward.
    # prev_min_D tracks the min D found at the previous (larger) α,
    # which is a LOWER bound for the current (smaller) α.
    prev_min_D = 1  # matching at large α achieves D=1

    # Upper α limit: no point going above matching_alpha for d_max > 1
    max_k = min(n - 1, matching_alpha + 1)

    for k in range(max_k, min_k - 1, -1):
        if k >= matching_alpha:
            # Matching always works: α=ceil(n/2), D=1
            # No solver call needed, handled by trivial points
            prev_min_D = 1
            continue

        # Binary search bounds:
        # lo = prev_min_D (from monotonicity: smaller α ⟹ min_D can't decrease)
        # hi = max_d_turan
        lo = max(prev_min_D, 1)
        hi = max_d_turan

        if lo > hi:
            # Impossible — skip
            continue

        best_D, best_adj, best_stats, tos, qt = _binary_search_min_d(
            n, k, lo, hi, time_limit
        )
        timeouts.extend(tos)
        total_time += qt

        if best_D is not None:
            method = best_stats.get("method", "unknown")
            iterations = best_stats.get("iterations", 0)
            achievable.append((k, best_D, best_adj, qt, method, iterations))
            prev_min_D = best_D  # tighten lower bound for next (smaller) α
            n_to = len(tos)
            to_str = f", timeouts={n_to}" if _VERBOSITY >= 1 and n_to > 0 else ""
            print(f"  n={n}, α≤{k}: min_D={best_D}, time={qt:.1f}s, method={method}{to_str}",
                  flush=True)
        else:
            # Distinguish timeout from infeasible
            has_timeouts = len(tos) > 0
            if has_timeouts:
                reason = "TIMEOUT"
            else:
                reason = "INFEASIBLE"
            print(f"  n={n}, α≤{k}: {reason}, stopping α search (time={qt:.1f}s)", flush=True)
            break

    # Add trivial points
    empty_adj = np.zeros((n, n), dtype=np.uint8)
    achievable.append((n, 0, empty_adj, 0.0, "trivial", 0))

    if n >= 2:
        match_adj = np.zeros((n, n), dtype=np.uint8)
        for i in range(0, n - 1, 2):
            match_adj[i, i + 1] = match_adj[i + 1, i] = 1
        achievable.append((matching_alpha, 1, match_adj, 0.0, "trivial", 0))

    # Deduplicate by (alpha, d_max)
    seen = set()
    deduped = []
    for entry in achievable:
        key = (entry[0], entry[1])
        if key not in seen:
            seen.add(key)
            deduped.append(entry)
    achievable = deduped

    # Extract Pareto frontier
    points = list(achievable)
    pareto = []
    for i, (a, d, adj, t, m, it) in enumerate(points):
        dominated = False
        for j, (a2, d2, *_) in enumerate(points):
            if i == j:
                continue
            if a2 <= a and d2 <= d and (a2 < a or d2 < d):
                dominated = True
                break
        if not dominated:
            pareto.append((a, d, adj, t, m, it))

    pareto.sort(key=lambda x: (x[0], x[1]))

    # Build result
    frontier = []
    for alpha, d_max, adj, solve_time, method, iterations in pareto:
        edges = adj_to_edge_list(adj)
        g6 = adj_to_g6(adj)
        c_log = None
        if d_max > 1:
            c_log = round(alpha * d_max / (n * log(d_max)), 4)
        frontier.append({
            "alpha": int(alpha),
            "d_max": int(d_max),
            "c_log": c_log,
            "edges": edges,
            "g6": g6,
            "solve_time": round(solve_time, 3),
            "method": method,
            "iterations": iterations,
        })

    c_values = [p["c_log"] for p in frontier if p["c_log"] is not None]
    min_c = min(c_values) if c_values else None

    return {
        "n": n,
        "time_limit": time_limit,
        "pareto_frontier": frontier,
        "min_c_log": min_c,
        "timeouts": timeouts,
        "total_time": round(total_time, 3),
    }


# --- Parallel execution across n values ---

def _run_single_n(n):
    """Worker function for parallel execution. Runs one n value."""
    tl = time_limit_for_n(n)
    t0 = time.time()
    result = scan_pareto_frontier_production(n, tl)
    wall_time = time.time() - t0
    result["wall_time"] = round(wall_time, 3)
    return n, result


# --- Summary and output ---

def load_brute_force(n: int) -> dict | None:
    path = f"{RESULTS_DIR}/brute_force_n{n}.json"
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def print_search_plan(n_values):
    """Dry-run: show what queries will be issued."""
    total_useful = 0
    print(f"{'n':>3} | {'min_α':>5} | {'max_α':>5} | {'max_D':>5} | {'tlimit':>6} | {'#useful_α':>9} | {'est_queries':>11}")
    print("-" * 70)
    for n in n_values:
        min_k = min_alpha_for_n(n)
        matching_alpha = (n + 1) // 2
        max_d = max_dmax_for_n(n)
        tl = time_limit_for_n(n)
        useful = matching_alpha - min_k
        import math
        queries = useful * (1 + math.ceil(math.log2(max(max_d, 2))))
        total_useful += useful
        print(f"{n:>3} | {min_k:>5} | {matching_alpha-1:>5} | {max_d:>5} | {tl:>5}s | {useful:>9} | {queries:>11}")
    print(f"\nTotal useful α queries: {total_useful}")


def run_production(n_values, dry_run=False, parallel=1, workers=8,
                   timeout=None, verbosity=0):
    """Main production sweep.

    Args:
        n_values: list of n values to compute
        dry_run: if True, only show search plan
        parallel: number of n values to run in parallel (1 = sequential)
        workers: number of CP-SAT solver workers per query
        timeout: override per-query time limit (seconds), None = use defaults
        verbosity: 0=default, 1=verbose, 2=extra verbose
    """
    global _VERBOSITY, _TIMEOUT_OVERRIDE
    _VERBOSITY = verbosity
    _TIMEOUT_OVERRIDE = timeout
    if dry_run:
        print_search_plan(n_values)
        return

    # Set solver workers globally
    import k4free_ilp.ilp_solver as solver_mod
    # Patch _solve_and_extract to use configured workers
    _orig_solve = solver_mod._solve_and_extract
    def _patched_solve(model, x, n, time_limit):
        from ortools.sat.python import cp_model as cpm
        solver = cpm.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_workers = workers
        t0 = time.time()
        result_status = solver.solve(model)
        solve_time = time.time() - t0
        if result_status in (cpm.OPTIMAL, cpm.FEASIBLE):
            adj = np.zeros((n, n), dtype=np.uint8)
            for (i, j), var in x.items():
                if solver.value(var):
                    adj[i, j] = adj[j, i] = 1
            return "FEASIBLE", adj, solve_time
        elif result_status == cpm.INFEASIBLE:
            return "INFEASIBLE", None, solve_time
        else:
            return "TIMEOUT", None, solve_time
    solver_mod._solve_and_extract = _patched_solve

    os.makedirs(RESULTS_DIR, exist_ok=True)
    all_results = {}

    # Load brute force results for n ≤ 10
    for n in range(3, 11):
        bf = load_brute_force(n)
        if bf:
            all_results[n] = bf
            all_results[n]["total_time"] = 0.0
            all_results[n]["timeouts"] = []
            all_results[n]["time_limit"] = 0

    # Run ILP for requested n values
    if parallel > 1:
        # Parallel execution: group n values and run concurrently.
        # Each process gets workers/parallel solver threads.
        print(f"Running {len(n_values)} n-values with parallelism={parallel}, "
              f"{workers} solver workers each", flush=True)
        # Process groups: run `parallel` n values simultaneously
        for batch_start in range(0, len(n_values), parallel):
            batch = n_values[batch_start:batch_start + parallel]
            print(f"\n--- Batch: n={batch} ---", flush=True)
            with ProcessPoolExecutor(max_workers=parallel) as executor:
                futures = {executor.submit(_run_single_n, n): n for n in batch}
                for future in as_completed(futures):
                    n, result = future.result()
                    path = f"{RESULTS_DIR}/pareto_n{n}.json"
                    with open(path, "w") as f:
                        json.dump(result, f, indent=2)
                    all_results[n] = result
                    _print_progress(n, result)
    else:
        for n in n_values:
            tl = time_limit_for_n(n)
            print(f"\n{'='*60}", flush=True)
            print(f"=== n={n}, time_limit={tl}s, workers={workers} ===", flush=True)
            print(f"    min_α={min_alpha_for_n(n)}, max_useful_α={min((n+1)//2 - 1, n-1)}, "
                  f"max_D={max_dmax_for_n(n)}", flush=True)
            print(f"{'='*60}", flush=True)

            t0 = time.time()
            result = scan_pareto_frontier_production(n, tl)
            wall_time = time.time() - t0
            result["wall_time"] = round(wall_time, 3)

            path = f"{RESULTS_DIR}/pareto_n{n}.json"
            with open(path, "w") as f:
                json.dump(result, f, indent=2)

            all_results[n] = result
            _print_progress(n, result)

    # Restore original solver
    solver_mod._solve_and_extract = _orig_solve

    # --- Final output ---
    _print_tables(all_results)


def _print_progress(n, result):
    """Print progress line for a completed n value."""
    frontier = result["pareto_frontier"]
    min_c = result["min_c_log"]
    best = None
    if min_c is not None:
        for p in frontier:
            if p["c_log"] == min_c:
                best = p
                break
    best_str = f"best=(α={best['alpha']}, d={best['d_max']})" if best else "no c_log"
    n_timeouts = len(result["timeouts"])
    wall = result.get("wall_time", result.get("total_time", 0))
    print(f"\nn={n}: {len(frontier)} Pareto points, min_c_log={min_c}, "
          f"{best_str}, wall={wall:.1f}s, timeouts={n_timeouts}",
          flush=True)


def _print_tables(all_results):
    """Print final summary tables."""
    print("\n" + "=" * 80)
    print("TABLE 1: Best c_log per n")
    print("=" * 80)
    print(f"{'n':>3} | {'min_α':>5} | {'d_at_min':>8} | {'min_c_log':>10} | {'method':>12} | {'solve_time':>10} | {'#pareto':>7}")
    print("-" * 75)

    best_per_n = []
    for n in sorted(all_results.keys()):
        res = all_results[n]
        frontier = res.get("pareto_frontier", [])
        min_c = res.get("min_c_log")
        best = None
        if min_c is not None:
            for p in frontier:
                if p["c_log"] == min_c:
                    best = p
                    break
        source = "brute" if n <= 10 else "ILP"
        method = best.get("method", source) if best else source
        st = best.get("solve_time", 0.0) if best else 0.0
        ba = best["alpha"] if best else "-"
        bd = best["d_max"] if best else "-"
        mc = f"{min_c:.4f}" if min_c is not None else "-"
        print(f"{n:>3} | {ba:>5} | {bd:>8} | {mc:>10} | {method:>12} | {st:>9.1f}s | {len(frontier):>7}")
        best_per_n.append({
            "n": n, "min_alpha": ba, "d_max": bd,
            "min_c_log": min_c, "method": method,
        })

    # Table 2: Interesting frontiers
    interesting_ns = [n for n in [24, 25, 30, 35] if n in all_results]
    interesting_frontiers = {}
    print("\n" + "=" * 80)
    print("TABLE 2: Full Pareto frontiers for interesting n values")
    print("=" * 80)
    for n in interesting_ns:
        res = all_results[n]
        frontier = res.get("pareto_frontier", [])
        interesting_frontiers[str(n)] = frontier
        print(f"\nn={n} Pareto frontier:")
        for p in frontier:
            c_str = f"{p['c_log']:.4f}" if p["c_log"] is not None else "  -   "
            e_count = len(p.get("edges", []))
            print(f"  α={p['alpha']:>2}, d={p['d_max']:>2}, c_log={c_str}, "
                  f"edges={e_count:>3}, method={p.get('method', '?')}")

    # Table 3: Trend analysis
    print("\n" + "=" * 80)
    print("TABLE 3: Trend analysis — min_c_log vs n")
    print("=" * 80)

    trend_data = []
    for n in sorted(all_results.keys()):
        mc = all_results[n].get("min_c_log")
        if mc is not None:
            trend_data.append((n, mc))

    if len(trend_data) >= 2:
        ns = np.array([x[0] for x in trend_data], dtype=float)
        cs = np.array([x[1] for x in trend_data], dtype=float)
        ln_ns = np.log(ns)

        A = np.vstack([ns, np.ones(len(ns))]).T
        slope_n, intercept_n = np.linalg.lstsq(A, cs, rcond=None)[0]
        residuals_n = cs - (slope_n * ns + intercept_n)
        ss_res_n = (residuals_n ** 2).sum()
        ss_tot = ((cs - cs.mean()) ** 2).sum()
        r2_n = 1 - ss_res_n / ss_tot if ss_tot > 0 else 0

        A2 = np.vstack([ln_ns, np.ones(len(ln_ns))]).T
        slope_ln, intercept_ln = np.linalg.lstsq(A2, cs, rcond=None)[0]
        residuals_ln = cs - (slope_ln * ln_ns + intercept_ln)
        ss_res_ln = (residuals_ln ** 2).sum()
        r2_ln = 1 - ss_res_ln / ss_tot if ss_tot > 0 else 0

        print(f"\nData points: {len(trend_data)}")
        print(f"\nc_log vs n:      slope={slope_n:.6f}, intercept={intercept_n:.4f}, R²={r2_n:.4f}")
        print(f"c_log vs ln(n):  slope={slope_ln:.6f}, intercept={intercept_ln:.4f}, R²={r2_ln:.4f}")

        print(f"\n{'n':>3} | {'min_c_log':>10} | {'predicted(n)':>12} | {'predicted(ln_n)':>15}")
        print("-" * 50)
        for n_val, c_val in trend_data:
            pred_n = slope_n * n_val + intercept_n
            pred_ln = slope_ln * log(n_val) + intercept_ln
            print(f"{n_val:>3} | {c_val:>10.4f} | {pred_n:>12.4f} | {pred_ln:>15.4f}")

        trend = {
            "vs_n": {"slope": round(slope_n, 6), "intercept": round(intercept_n, 4), "r_squared": round(r2_n, 4)},
            "vs_ln_n": {"slope": round(slope_ln, 6), "intercept": round(intercept_ln, 4), "r_squared": round(r2_ln, 4)},
        }
    else:
        trend = {}
        print("Not enough data points for trend analysis.")

    # Save summary
    summary = {
        "best_per_n": best_per_n,
        "interesting_frontiers": interesting_frontiers,
        "trend": trend,
    }
    with open(f"{RESULTS_DIR}/summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    # Export low c_log graphs
    with open(f"{RESULTS_DIR}/low_c_graphs.g6", "w") as f:
        for n in sorted(all_results.keys()):
            frontier = all_results[n].get("pareto_frontier", [])
            for p in frontier:
                if p.get("c_log") is not None and p["c_log"] < 0.8:
                    f.write(f"# n={n}, α={p['alpha']}, d_max={p['d_max']}, c_log={p['c_log']}\n")
                    f.write(f"{p['g6']}\n")

    print(f"\nResults saved to {RESULTS_DIR}/summary.json")
    print(f"Low c_log graphs saved to {RESULTS_DIR}/low_c_graphs.g6")


def main():
    parser = argparse.ArgumentParser(description="Production Pareto frontier sweep")
    parser.add_argument("n_values", nargs="*", type=int,
                        help="Specific n values to run (default: 11..35)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show search plan without solving")
    parser.add_argument("--parallel", type=int, default=1,
                        help="Number of n values to run in parallel (default: 1)")
    parser.add_argument("--workers", type=int, default=8,
                        help="CP-SAT solver workers per query (default: 8)")
    parser.add_argument("--timeout", type=int, default=None,
                        help="Override per-query time limit in seconds (default: 300 for n≤20, 600 for n>20)")
    parser.add_argument("-v", "--verbose", action="count", default=0,
                        help="Increase verbosity (-v: show timeouts/infeasible, -vv: log every query)")
    args = parser.parse_args()

    n_values = args.n_values if args.n_values else list(range(11, 36))
    run_production(n_values, dry_run=args.dry_run,
                   parallel=args.parallel, workers=args.workers,
                   timeout=args.timeout, verbosity=args.verbose)


if __name__ == "__main__":
    main()
