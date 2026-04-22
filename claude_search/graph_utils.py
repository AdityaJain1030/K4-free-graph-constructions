"""Graph utilities for K4-free graph optimization.

alpha_exact, alpha_sat, _sat_check_is, is_k4_free, compute_c_value copied
verbatim from experiments/block_decomposition/run_experiment.py (lines 63-251).
Edge-list wrappers (edges_to_adj, is_k4_free_edges, greedy_mis, graph_metrics,
compute_alpha) are new to this module.
"""

import math
import threading
import time

import numpy as np
import networkx as nx

from pysat.card import CardEnc, EncType
from pysat.solvers import Glucose4


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


def alpha_cpsat(adj, timeout=60):
    """Exact α via OR-Tools CP-SAT. Returns (alpha, time_s, timed_out).

    CP-SAT solves the MIS directly as a 0/1 maximization (x_i + x_j ≤ 1
    per edge, maximize Σ x_i) rather than the SAT binary-search over the
    cardinality constraint used by `alpha_sat`. On the K₄-free sparse
    graphs this pipeline evaluates, CP-SAT is 5–20× faster at N ≥ 50
    and scales well past N = 100 because the integer presolve plus
    internal parallel search workers (up to 8) handle this exact shape
    well.

    On timeout returns (best_feasible_alpha_or_0, elapsed, True) —
    compute_alpha then falls back to greedy as a lower bound.
    """
    from ortools.sat.python import cp_model
    import os as _os

    n = int(adj.shape[0])
    t0 = time.time()
    model = cp_model.CpModel()
    x = [model.new_bool_var(f"x_{i}") for i in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if adj[i, j]:
                model.add(x[i] + x[j] <= 1)
    model.maximize(sum(x))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = float(timeout)
    solver.parameters.num_search_workers = min(8, (_os.cpu_count() or 4))
    solver.parameters.log_search_progress = False

    status = solver.solve(model)
    elapsed = time.time() - t0
    if status == cp_model.OPTIMAL:
        return int(round(solver.objective_value)), elapsed, False
    if status == cp_model.FEASIBLE:
        # Feasible but not proven optimal — treat as timeout, caller
        # will take max with greedy_mis and mark alpha_exact=False.
        return int(round(solver.objective_value)), elapsed, True
    # INFEASIBLE can't happen here (x all 0 is always feasible); treat
    # any other status (UNKNOWN, etc.) as timeout with alpha=0.
    return 0, elapsed, True


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
        remaining = max(0.1, timeout - (time.time() - t0))
        sat, to = _sat_check_is(n, edges, mid, remaining)
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


def compute_c_value(alpha, n, d_max):
    if d_max <= 1:
        return float("inf")
    return alpha * d_max / (n * math.log(d_max))


# ----------------------------------------------------------------------------
# Edge-list interface (what construct(N) returns)
# ----------------------------------------------------------------------------


def edges_to_adj(edges, N):
    """Validate and convert edge list to symmetric bool adjacency matrix.

    Raises ValueError with a specific reason on malformed input.
    """
    if not isinstance(edges, (list, tuple)):
        raise ValueError(f"edges must be list/tuple, got {type(edges).__name__}")
    adj = np.zeros((N, N), dtype=np.bool_)
    for idx, e in enumerate(edges):
        if not isinstance(e, (tuple, list)) or len(e) != 2:
            raise ValueError(f"edge {idx} is not a 2-element sequence: {e!r}")
        i, j = e
        if not isinstance(i, (int, np.integer)) or not isinstance(j, (int, np.integer)):
            raise ValueError(f"edge {idx} contains non-int vertex: {e!r}")
        i, j = int(i), int(j)
        if i < 0 or j < 0 or i >= N or j >= N:
            raise ValueError(f"edge {idx} vertex out of range [0,{N}): {e!r}")
        if i == j:
            raise ValueError(f"edge {idx} is a self-loop: {e!r}")
        adj[i, j] = True
        adj[j, i] = True
    return adj


def is_k4_free_edges(edges, N):
    """Edge-list wrapper around is_k4_free."""
    adj = edges_to_adj(edges, N)
    return is_k4_free(adj)


def greedy_mis(edges, N):
    """Greedy independent set (lower bound on alpha). Returns vertex list."""
    adj = edges_to_adj(edges, N)
    degrees = adj.sum(axis=1)
    order = sorted(range(N), key=lambda v: degrees[v])
    selected = []
    blocked = np.zeros(N, dtype=np.bool_)
    for v in order:
        if not blocked[v]:
            selected.append(v)
            blocked[v] = True
            for u in range(N):
                if adj[v, u]:
                    blocked[u] = True
    return selected


def graph_metrics(edges, N):
    """Single-pass metrics on an edge list. Assumes edges_to_adj succeeds."""
    adj = edges_to_adj(edges, N)
    degrees = adj.sum(axis=1).astype(int)
    d_max = int(degrees.max()) if N > 0 else 0
    d_min = int(degrees.min()) if N > 0 else 0
    d_mean = float(degrees.mean()) if N > 0 else 0.0
    degree_variance = float(degrees.var()) if N > 0 else 0.0
    edge_count = int(adj.sum() // 2)
    edge_density = (2.0 * edge_count) / (N * (N - 1)) if N >= 2 else 0.0
    if d_mean > 0:
        regularity_score = 1.0 - (d_max - d_min) / d_mean
    else:
        regularity_score = 1.0 if d_max == d_min else 0.0

    # Triangle count via bitmask
    nbr = [0] * N
    for i in range(N):
        for j in range(N):
            if adj[i, j]:
                nbr[i] |= 1 << j
    tri = 0
    for a in range(N):
        for b in range(a + 1, N):
            if adj[a, b]:
                common = nbr[a] & nbr[b]
                # count bits > b in common
                mask = common & ~((1 << (b + 1)) - 1)
                tri += bin(mask).count("1")

    # is_connected via networkx
    G = nx.Graph()
    G.add_nodes_from(range(N))
    for i in range(N):
        for j in range(i + 1, N):
            if adj[i, j]:
                G.add_edge(i, j)
    is_conn = bool(nx.is_connected(G)) if N > 0 else True

    return {
        "d_max": d_max,
        "d_min": d_min,
        "d_mean": d_mean,
        "degree_variance": degree_variance,
        "regularity_score": regularity_score,
        "edge_count": edge_count,
        "edge_density": edge_density,
        "triangle_count": tri,
        "is_connected": is_conn,
        "degree_sequence": sorted(degrees.tolist(), reverse=True),
    }


def compute_alpha(edges, N, timeout):
    """Compute independence number, exact if possible, else greedy lower bound.

    Returns (alpha, exact_bool, elapsed_s).

    Solver choice: bitmask B&B for N ≤ 20 (fastest there); CP-SAT
    otherwise. CP-SAT replaced the older pysat binary-search because it
    is 5–20× faster on the sparse K₄-free graphs this pipeline sees and
    scales past N = 100 where the binary search stalled.
    """
    adj = edges_to_adj(edges, N)
    t0 = time.time()
    if N <= 20:
        a, _ = alpha_exact(adj)
        return a, True, time.time() - t0
    a, _elapsed, timed_out = alpha_cpsat(adj, timeout=timeout)
    if timed_out:
        mis = greedy_mis(edges, N)
        lb = len(mis)
        # CP-SAT's feasible-but-not-optimal value is a valid lower bound;
        # take the max with greedy.
        a = max(a, lb)
        return a, False, time.time() - t0
    return a, True, time.time() - t0
