"""CP-SAT ILP solver for K₄-free graph decision problems."""

import time
from itertools import combinations
from math import comb

import numpy as np
from ortools.sat.python import cp_model

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from k4free_ilp.k4_check import is_k4_free
from k4free_ilp.alpha_exact import alpha_exact
from utils.ramsey import KNOWN_RAMSEY, degree_bounds as _ramsey_degree_bounds

# Configurable threshold: C(n, alpha+1) above this triggers lazy solver
_LAZY_THRESHOLD = 5_000_000


def _generate_hint(n: int, target_degree: int) -> np.ndarray:
    """Generate a dense graph hint using a Paley-like circulant construction.

    Creates a circulant graph on n vertices where vertex i connects to j
    when (i-j) mod n is a quadratic residue mod p (for largest prime p ≤ n).
    This provides a reasonable starting point for the solver.
    """
    def is_prime(x):
        if x < 2:
            return False
        for d in range(2, int(x**0.5) + 1):
            if x % d == 0:
                return False
        return True

    # Find largest prime p ≤ n
    p = n
    while p > 2 and not is_prime(p):
        p -= 1

    # Quadratic residues mod p
    qr = set()
    for i in range(1, p):
        qr.add((i * i) % p)

    adj = np.zeros((n, n), dtype=np.uint8)
    for i in range(p):
        for j in range(i + 1, p):
            diff = (j - i) % p
            if diff in qr and diff != 0:
                adj[i, j] = adj[j, i] = 1

    # Trim edges to approximate target degree
    degrees = adj.sum(axis=1)
    for i in range(n):
        if degrees[i] > target_degree:
            neighbors = [j for j in range(n) if adj[i, j]]
            import random
            random.seed(42 + i)
            random.shuffle(neighbors)
            for j in neighbors:
                if degrees[i] <= target_degree:
                    break
                adj[i, j] = adj[j, i] = 0
                degrees[i] -= 1
                degrees[j] -= 1

    return adj


def _build_model(n, max_degree, edge_cuts=None, enumerate_alpha_k=None,
                 min_degree=0, symmetry_breaking=True, hint_adj=None):
    """Build a CP-SAT model with K₄-free + degree constraints.

    Args:
        n: number of vertices
        max_degree: maximum degree constraint
        edge_cuts: list of lists of (i,j) edge pairs to add as cutting planes
        enumerate_alpha_k: if set, enumerate all k-subsets and add independence constraints
        min_degree: minimum degree constraint (from Ramsey bounds)
        symmetry_breaking: if True, add degree-ordering symmetry breaking
        hint_adj: optional adjacency matrix to use as solution hint

    Returns:
        (model, x_dict, edge_vars_list)
    """
    model = cp_model.CpModel()

    x = {}
    edge_vars = []
    for i in range(n):
        for j in range(i + 1, n):
            x[(i, j)] = model.new_bool_var(f"x_{i}_{j}")
            edge_vars.append(x[(i, j)])

    # Solution hint
    if hint_adj is not None:
        for (i, j), var in x.items():
            model.add_hint(var, int(hint_adj[i, j]))

    # K₄-free constraints
    for a, b, c, d in combinations(range(n), 4):
        model.add(
            x[(a, b)] + x[(a, c)] + x[(a, d)]
            + x[(b, c)] + x[(b, d)] + x[(c, d)] <= 5
        )

    # Degree constraints
    for i in range(n):
        incident = [x[(min(i, j), max(i, j))] for j in range(n) if j != i]
        model.add(sum(incident) <= max_degree)
        if min_degree > 0:
            model.add(sum(incident) >= min_degree)

    # Symmetry breaking: degree(i) >= degree(i+1)
    if symmetry_breaking:
        for i in range(n - 1):
            inc_i = [x[(min(i, j), max(i, j))] for j in range(n) if j != i]
            inc_next = [x[(min(i + 1, j), max(i + 1, j))] for j in range(n) if j != i + 1]
            model.add(sum(inc_i) >= sum(inc_next))

    # Direct enumeration of independence constraints
    if enumerate_alpha_k is not None and enumerate_alpha_k <= n:
        for subset in combinations(range(n), enumerate_alpha_k):
            edges_in_subset = []
            for ii in range(len(subset)):
                for jj in range(ii + 1, len(subset)):
                    edges_in_subset.append(x[(subset[ii], subset[jj])])
            model.add(sum(edges_in_subset) >= 1)

    # Lazy cutting plane constraints
    if edge_cuts:
        for cut_edges in edge_cuts:
            constraint_vars = [x[(min(i, j), max(i, j))] for i, j in cut_edges]
            model.add(sum(constraint_vars) >= 1)

    # Decision strategy
    model.add_decision_strategy(
        edge_vars,
        cp_model.CHOOSE_FIRST,
        cp_model.SELECT_MAX_VALUE,
    )

    return model, x, edge_vars


def _solve_and_extract(model, x, n, time_limit):
    """Solve a model and extract the adjacency matrix if feasible.

    Returns (status_str, adj_or_none, solve_time)
    """
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 8

    t0 = time.time()
    result_status = solver.solve(model)
    solve_time = time.time() - t0

    if result_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        adj = np.zeros((n, n), dtype=np.uint8)
        for (i, j), var in x.items():
            if solver.value(var):
                adj[i, j] = adj[j, i] = 1
        return "FEASIBLE", adj, solve_time
    elif result_status == cp_model.INFEASIBLE:
        return "INFEASIBLE", None, solve_time
    else:
        return "TIMEOUT", None, solve_time


def _effective_degree_bounds(n, max_alpha, max_degree):
    """Compute effective min/max degree using Ramsey-derived bounds."""
    ramsey_min, ramsey_max = _ramsey_degree_bounds(n, max_alpha)
    eff_min = ramsey_min if ramsey_min > 0 else 0
    eff_max = min(max_degree, ramsey_max) if ramsey_max > 0 else max_degree
    return eff_min, eff_max


def solve_k4free_direct(n: int, max_alpha: int, max_degree: int,
                        time_limit: int = 300) -> tuple[str, np.ndarray | None, dict]:
    """Solve using direct enumeration of all (max_alpha+1)-subsets."""
    k = max_alpha + 1
    num_subsets = comb(n, k) if k <= n else 0
    if num_subsets > 5_000_000:
        print(f"  WARNING: C({n},{k}) = {num_subsets} > 5M independence constraints")

    eff_min, eff_max = _effective_degree_bounds(n, max_alpha, max_degree)

    # Quick infeasibility check from Ramsey bounds
    if eff_min > eff_max:
        return "INFEASIBLE", None, {
            "solve_time": 0.0, "iterations": 0,
            "method": "direct_enumeration (Ramsey bound)",
        }

    # For larger instances, disable symmetry breaking and add a hint
    use_sym = n <= 15
    hint = _generate_hint(n, (eff_min + eff_max) // 2) if n > 15 else None

    model, x, edge_vars = _build_model(n, eff_max, enumerate_alpha_k=k,
                                        min_degree=eff_min,
                                        symmetry_breaking=use_sym,
                                        hint_adj=hint)

    status, adj, solve_time = _solve_and_extract(model, x, n, time_limit)

    stats = {
        "solve_time": round(solve_time, 3),
        "iterations": 0,
        "method": "direct_enumeration",
    }

    if status == "FEASIBLE":
        assert is_k4_free(adj), "Solver returned graph with K₄!"
        actual_alpha, _ = alpha_exact(adj)
        actual_dmax = int(adj.sum(axis=1).max())
        assert actual_alpha <= max_alpha, (
            f"Solver α={actual_alpha} > max_alpha={max_alpha}"
        )
        assert actual_dmax <= max_degree, (
            f"Solver d_max={actual_dmax} > max_degree={max_degree}"
        )

    return status, adj, stats


def solve_k4free_lazy(n: int, max_alpha: int, max_degree: int,
                      time_limit: int = 600, max_iterations: int = 200,
                      max_cuts_per_iter: int = 1,
                      ) -> tuple[str, np.ndarray | None, dict]:
    """
    Same interface as solve_k4free, but uses lazy cutting planes for α.

    Iteratively solves, checks α, and adds violated independent set constraints.
    When max_cuts_per_iter > 1, finds multiple violated independent sets per
    iteration to converge faster.
    """
    eff_min, eff_max = _effective_degree_bounds(n, max_alpha, max_degree)

    if eff_min > eff_max:
        return "INFEASIBLE", None, {
            "solve_time": 0.0, "iterations": 0, "constraints_added": 0,
            "alpha_sequence": [], "method": "lazy (Ramsey bound)",
        }

    cuts = []
    alpha_sequence = []
    cumulative_time = 0.0

    for iteration in range(1, max_iterations + 1):
        remaining_time = time_limit - cumulative_time
        if remaining_time <= 0:
            stats = {
                "solve_time": round(cumulative_time, 3),
                "iterations": iteration - 1,
                "constraints_added": len(cuts),
                "alpha_sequence": alpha_sequence,
                "method": "lazy",
            }
            return "TIMEOUT", None, stats

        use_sym = n <= 15
        hint = _generate_hint(n, (eff_min + eff_max) // 2) if n > 15 else None
        model, x, edge_vars = _build_model(n, eff_max, edge_cuts=cuts,
                                            min_degree=eff_min,
                                            symmetry_breaking=use_sym,
                                            hint_adj=hint)
        status, adj, solve_time = _solve_and_extract(model, x, n, remaining_time)
        cumulative_time += solve_time

        if status == "INFEASIBLE":
            stats = {
                "solve_time": round(cumulative_time, 3),
                "iterations": iteration,
                "constraints_added": len(cuts),
                "alpha_sequence": alpha_sequence,
                "method": "lazy",
            }
            print(f"  Iteration {iteration}: INFEASIBLE, constraints={len(cuts)}, time={cumulative_time:.1f}s")
            return "INFEASIBLE", None, stats

        if status == "TIMEOUT":
            stats = {
                "solve_time": round(cumulative_time, 3),
                "iterations": iteration,
                "constraints_added": len(cuts),
                "alpha_sequence": alpha_sequence,
                "method": "lazy",
            }
            return "TIMEOUT", None, stats

        # Feasible — check α
        assert is_k4_free(adj), "Solver returned graph with K₄!"
        actual_alpha, indep_set = alpha_exact(adj)
        actual_dmax = int(adj.sum(axis=1).max())
        alpha_sequence.append(actual_alpha)

        print(f"  Iteration {iteration}: α={actual_alpha}, target≤{max_alpha}, "
              f"constraints={len(cuts)}, time={cumulative_time:.1f}s", flush=True)

        if actual_alpha <= max_alpha:
            assert actual_dmax <= max_degree, (
                f"Solver d_max={actual_dmax} > max_degree={max_degree}"
            )
            stats = {
                "solve_time": round(cumulative_time, 3),
                "iterations": iteration,
                "constraints_added": len(cuts),
                "alpha_sequence": alpha_sequence,
                "method": "lazy",
            }
            return "FEASIBLE", adj, stats

        # Add cutting planes: find violated independent sets and forbid them
        def _add_cut_from_indep(indep):
            cut_edges = []
            for ii in range(len(indep)):
                for jj in range(ii + 1, len(indep)):
                    u, v = indep[ii], indep[jj]
                    cut_edges.append((min(u, v), max(u, v)))
            cuts.append(cut_edges)

        _add_cut_from_indep(indep_set)

        # Try to find additional violated independent sets on the same graph
        if max_cuts_per_iter > 1:
            remaining_adj = adj.copy()
            used_vertices = set(indep_set)
            for _ in range(max_cuts_per_iter - 1):
                # Mask out vertices from previous independent sets
                sub_adj = remaining_adj.copy()
                for v in used_vertices:
                    sub_adj[v, :] = 0
                    sub_adj[:, v] = 0
                remaining_n = int((sub_adj.sum(axis=1) > 0).sum()) + \
                              (sub_adj.shape[0] - len(used_vertices))
                if remaining_n <= max_alpha:
                    break
                sub_alpha, sub_indep = alpha_exact(sub_adj)
                if sub_alpha <= max_alpha:
                    break
                _add_cut_from_indep(sub_indep)
                used_vertices.update(sub_indep)

    # Max iterations reached
    stats = {
        "solve_time": round(cumulative_time, 3),
        "iterations": max_iterations,
        "constraints_added": len(cuts),
        "alpha_sequence": alpha_sequence,
        "method": "lazy",
    }
    return "TIMEOUT", None, stats


def solve_k4free(n: int, max_alpha: int, max_degree: int,
                 time_limit: int = 300,
                 strategy: str = "auto",
                 lazy_max_iters: int = 200,
                 lazy_max_cuts: int = 1,
                 ) -> tuple[str, np.ndarray | None, dict]:
    """
    Auto-selecting solver: uses direct enumeration if C(n, max_alpha+1) <= threshold,
    otherwise uses lazy cutting planes. Applies Ramsey-derived degree bounds.

    Args:
        strategy: "auto" (default), "direct", or "lazy"
        lazy_max_iters: max iterations for lazy solver
        lazy_max_cuts: max violated independent sets to add per lazy iteration
    """
    k = max_alpha + 1
    num_subsets = comb(n, k) if k <= n else 0

    if strategy == "direct":
        use_direct = True
    elif strategy == "lazy":
        use_direct = False
    else:
        use_direct = num_subsets <= _LAZY_THRESHOLD

    if use_direct:
        return solve_k4free_direct(n, max_alpha, max_degree, time_limit)
    else:
        print(f"  Using lazy solver: C({n},{k}) = {num_subsets} > {_LAZY_THRESHOLD}", flush=True)
        return solve_k4free_lazy(n, max_alpha, max_degree, time_limit,
                                  max_iterations=lazy_max_iters,
                                  max_cuts_per_iter=lazy_max_cuts)
