"""CP-SAT solver for minimum-edge K₄-free graphs with bounded independence number.

Exploits Hajnal's theorem: the optimal graph is near-regular (all vertex degrees
are D or D+1 for some integer D). We iterate D upward from the Ramsey lower bound;
the first feasible D gives the minimum-edge graph (since edge ranges for consecutive
D values don't overlap). Each step is a pure feasibility check — no optimization.
"""

import sys
import os
import time
from itertools import combinations
from math import comb

import numpy as np
from ortools.sat.python import cp_model

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from k4free_ilp.alpha_exact import alpha_exact
from k4free_ilp.k4_check import is_k4_free
from k4free_ilp.graph_io import adj_to_g6

KNOWN_RAMSEY = {
    (3, 3): 6, (3, 4): 9, (3, 5): 14, (3, 6): 18, (3, 7): 23, (3, 8): 28, (3, 9): 36,
    (4, 3): 9, (4, 4): 18, (4, 5): 25,
}
for (s, t), v in list(KNOWN_RAMSEY.items()):
    KNOWN_RAMSEY[(t, s)] = v

_LAZY_THRESHOLD = 5_000_000


def _degree_bounds(n, max_alpha):
    """Ramsey-based bounds on the base degree D: (d_lo, d_hi)."""
    r4a = KNOWN_RAMSEY.get((4, max_alpha))
    d_lo = max(0, n - r4a) if r4a is not None else 0
    r3a1 = KNOWN_RAMSEY.get((3, max_alpha + 1))
    d_hi = r3a1 - 1 if r3a1 is not None else n - 1
    return d_lo, d_hi


def _build_model(n, max_alpha, D, enumerate_alpha=False, alpha_cuts=None):
    """Build CP-SAT feasibility model for a fixed base degree D.

    Constraints: K₄-free, deg(v) ∈ {D, D+1}, α ≤ max_alpha. No objective.
    """
    model = cp_model.CpModel()

    # Edge variables
    x = {}
    for i in range(n):
        for j in range(i + 1, n):
            x[(i, j)] = model.new_bool_var(f"e{i}_{j}")

    # K₄-free: each 4-subset has at most 5 of 6 edges
    for a, b, c, d in combinations(range(n), 4):
        model.add(
            x[(a, b)] + x[(a, c)] + x[(a, d)]
            + x[(b, c)] + x[(b, d)] + x[(c, d)] <= 5
        )

    # Near-regularity: deg(v) ∈ {D, D+1}
    for v in range(n):
        inc = [x[(min(v, j), max(v, j))] for j in range(n) if j != v]
        model.add(sum(inc) >= D)
        model.add(sum(inc) <= D + 1)

    # α constraints (direct enumeration)
    if enumerate_alpha:
        k = max_alpha + 1
        for subset in combinations(range(n), k):
            edges = [x[(subset[a], subset[b])]
                     for a in range(len(subset)) for b in range(a + 1, len(subset))]
            model.add(sum(edges) >= 1)

    # α constraints (lazy cuts from prior iterations)
    if alpha_cuts:
        for iset in alpha_cuts:
            edges = [x[tuple(sorted((iset[a], iset[b])))]
                     for a in range(len(iset)) for b in range(a + 1, len(iset))]
            model.add(sum(edges) >= 1)

    return model, x


def _solve(model, x, n, time_limit, num_workers):
    """Run CP-SAT solver and extract adjacency matrix."""
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = num_workers

    status = solver.solve(model)

    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        adj = np.zeros((n, n), dtype=np.uint8)
        for (i, j), var in x.items():
            if solver.value(var):
                adj[i, j] = adj[j, i] = 1
        return "FEASIBLE", adj
    elif status == cp_model.INFEASIBLE:
        return "INFEASIBLE", None
    else:
        return "TIMEOUT", None


def _validate(adj, n, max_alpha):
    """Assert K₄-free, α bound, and near-regularity. Return actual α."""
    assert is_k4_free(adj), "BUG: K₄ found"
    alpha, _ = alpha_exact(adj)
    assert alpha <= max_alpha, f"BUG: α={alpha} > {max_alpha}"
    degs = adj.sum(axis=1)
    assert int(degs.max()) - int(degs.min()) <= 1, (
        f"BUG: not near-regular, degrees {sorted(set(int(d) for d in degs))}"
    )
    return alpha


def _result(status, adj, n, max_alpha, D, elapsed, method, iterations):
    """Package result dict, validating if a solution exists."""
    if adj is None:
        return {
            "status": status, "adjacency": None, "num_edges": None,
            "degree_sequence": None, "alpha": None, "D": D,
            "solve_time": round(elapsed, 3), "method": method,
            "iterations": iterations, "g6": None,
        }
    alpha = _validate(adj, n, max_alpha)
    degs = sorted(adj.sum(axis=1).astype(int).tolist())
    ne = int(adj.sum()) // 2
    return {
        "status": status, "adjacency": adj.tolist(), "num_edges": ne,
        "degree_sequence": degs, "alpha": alpha, "D": degs[0],
        "solve_time": round(elapsed, 3), "method": method,
        "iterations": iterations, "g6": adj_to_g6(adj),
    }


def _solve_for_D_direct(n, max_alpha, D, time_limit, num_workers):
    """Feasibility check for a fixed D with direct α enumeration."""
    model, x = _build_model(n, max_alpha, D, enumerate_alpha=True)
    return _solve(model, x, n, time_limit, num_workers)


def _solve_for_D_lazy(n, max_alpha, D, time_limit, num_workers):
    """Feasibility check for a fixed D with lazy α cutting planes."""
    t0 = time.time()
    alpha_cuts = []

    for iteration in range(1, 500):
        remaining = time_limit - (time.time() - t0)
        if remaining <= 1:
            return "TIMEOUT", None, iteration

        model, x = _build_model(n, max_alpha, D, alpha_cuts=alpha_cuts)
        status, adj = _solve(model, x, n, remaining, num_workers)

        if adj is None:
            return status, None, iteration

        actual_alpha, indep_set = alpha_exact(adj)
        print(f"    lazy iter {iteration}: α={actual_alpha}, "
              f"edges={int(adj.sum())//2}", flush=True)

        if actual_alpha <= max_alpha:
            return "FEASIBLE", adj, iteration

        alpha_cuts.append(indep_set)

    return "TIMEOUT", None, 500


def solve_min_edges(n: int, max_alpha: int, time_limit: int = 600,
                    num_workers: int = None) -> dict:
    """Find minimum-edge K₄-free graph on n vertices with α ≤ max_alpha.

    Iterates D upward from Ramsey lower bound. First feasible D is optimal
    (edge ranges for consecutive D don't overlap).

    Returns dict with: status, adjacency, num_edges, degree_sequence,
    alpha, D, solve_time, method, iterations, g6.
    """
    if num_workers is None:
        num_workers = os.cpu_count() or 8
    t0 = time.time()

    d_lo, d_hi = _degree_bounds(n, max_alpha)
    k = max_alpha + 1
    direct = (k > n) or (comb(n, k) <= _LAZY_THRESHOLD)
    method_name = "cpsat_direct" if direct else "cpsat_lazy"

    print(f"solve_min_edges(n={n}, α≤{max_alpha}): D∈[{d_lo},{d_hi}], "
          f"{'direct' if direct else 'lazy'}, workers={num_workers}", flush=True)

    # Per-D log file
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, f"n{n}_a{max_alpha}_Dlog.csv")
    write_header = not os.path.exists(log_path)
    log_file = open(log_path, "a")
    if write_header:
        log_file.write("n,max_alpha,D,status,budget_s,elapsed_s,iterations,edges,method\n")
        log_file.flush()

    if d_lo > d_hi:
        elapsed = time.time() - t0
        print(f"  INFEASIBLE by Ramsey bounds", flush=True)
        log_file.close()
        return _result("INFEASIBLE", None, n, max_alpha, None, elapsed, "ramsey", 0)

    all_infeasible = True  # track whether all lower D values were proved infeasible

    for D in range(d_lo, d_hi + 1):
        remaining = time_limit - (time.time() - t0)
        if remaining <= 1:
            elapsed = time.time() - t0
            print(f"  D={D}: out of time", flush=True)
            log_file.write(f"{n},{max_alpha},{D},OUT_OF_TIME,0,{elapsed:.1f},0,,{method_name}\n")
            log_file.flush()
            log_file.close()
            return _result("TIMEOUT", None, n, max_alpha, D, elapsed, method_name, 0)

        # Budget: split remaining time among remaining D values
        D_left = d_hi + 1 - D
        budget = remaining / D_left
        print(f"  D={D} (budget {budget:.0f}s)...", end=" ", flush=True)

        d_t0 = time.time()
        if direct:
            status, adj = _solve_for_D_direct(n, max_alpha, D, budget, num_workers)
            iterations = 0
        else:
            status, adj, iterations = _solve_for_D_lazy(
                n, max_alpha, D, budget, num_workers)

        d_elapsed = time.time() - d_t0
        elapsed = time.time() - t0

        if status == "FEASIBLE" and adj is not None:
            ne = int(adj.sum()) // 2
            print(f"FEASIBLE, edges={ne} ({elapsed:.1f}s total)", flush=True)
            result_status = "OPTIMAL" if all_infeasible else "FEASIBLE"
            log_file.write(f"{n},{max_alpha},{D},{result_status},{budget:.1f},{d_elapsed:.1f},{iterations},{ne},{method_name}\n")
            log_file.flush()
            log_file.close()
            return _result(result_status, adj, n, max_alpha, D, elapsed,
                           method_name, iterations)

        if status == "TIMEOUT":
            all_infeasible = False
            print(f"TIMEOUT ({elapsed:.1f}s total)", flush=True)
        else:
            print(f"INFEASIBLE ({elapsed:.1f}s total)", flush=True)

        log_file.write(f"{n},{max_alpha},{D},{status},{budget:.1f},{d_elapsed:.1f},{iterations},,{method_name}\n")
        log_file.flush()

    # All D values exhausted
    elapsed = time.time() - t0
    final_status = "INFEASIBLE" if all_infeasible else "UNKNOWN"
    print(f"  All D values exhausted: {final_status}", flush=True)
    log_file.close()
    return _result(final_status, None, n, max_alpha, None, elapsed,
                   method_name, 0)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Find minimum-edge K₄-free graph")
    parser.add_argument("n", type=int)
    parser.add_argument("max_alpha", type=int)
    parser.add_argument("--time-limit", type=int, default=600)
    parser.add_argument("--workers", type=int, default=None)
    args = parser.parse_args()

    result = solve_min_edges(args.n, args.max_alpha, args.time_limit, args.workers)
    print(f"\nResult: {result['status']}")
    if result["num_edges"] is not None:
        print(f"  Edges: {result['num_edges']}")
        print(f"  Alpha: {result['alpha']}")
        print(f"  Degrees: {result['degree_sequence']}")
        print(f"  g6: {result['g6']}")
    print(f"  Time: {result['solve_time']:.1f}s")
    print(f"  Method: {result['method']}, iterations: {result['iterations']}")
