#!/usr/bin/env python3
"""
scripts/run_sat_circulant_optimal.py
====================================
SAT-based optimal K4-free circulant search with:

  1. Warm-start from CirculantSearchFast (DFS with |S|≤6).
  2. Hoffman eigenvalue constraint encoded directly in CP-SAT.
  3. α_target iteration per degree (not CEGAR MIS-blocking) — each SAT
     call is a decision problem "does there exist a K4-free circulant
     at degree d with Hoffman-certified α ≤ α_target?".

Hoffman constraint for circulants
---------------------------------
C(N, S) has eigenvalues λ_j(S) = Σ_k c_jk · g_k where
    c_jk = 2·cos(2π j k / N)   for k < N/2
         = cos(π j)            for k = N/2 (N even, single term)

Hoffman: α(G) ≤ -N·λ_min / (d - λ_min). Inverting, α ≤ α_target iff
    λ_min ≥ T(α_target) = -α_target · d / (N - α_target)

so we add one linear constraint per frequency j ∈ [1, ⌊N/2⌋]:
    Σ_k c_jk · g_k ≥ T(α_target)

integer-scaled by 1e4. Enforcing this makes every SAT solution S satisfy
Hoffman's certificate, so α(G(S)) ≤ α_target automatically — no CEGAR
inner loop needed. UNSAT means no Hoffman-certifiable circulant exists
at that (d, α_target) pair; a circulant with loose Hoffman bound might
still achieve α ≤ α_target but we skip those (rare in practice for
optimal circulants).

Usage:
    micromamba run -n k4free python scripts/run_sat_circulant_optimal.py \
        --n-min 10 --n-max 100 --save
"""

import argparse
import math
import os
import sys
import time
from math import ceil, log, cos, pi

import numpy as np
import networkx as nx
from ortools.sat.python import cp_model

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS
from search import CirculantSearchFast
from search.sat_circulant import _k4_gap_clauses, _circulant_graph, _circulant_adj
from utils.graph_props import alpha_cpsat, c_log_value


SCALE = 10000


def _hoffman_threshold_int(n: int, d: int, alpha_target: int) -> int:
    """Integer-scaled Hoffman threshold T(α_target) = -α_target·d/(N-α_target)."""
    if alpha_target >= n:
        return -(d * SCALE)  # trivially satisfied
    if n - alpha_target == 0:
        return -(d * SCALE)
    T = -alpha_target * d / (n - alpha_target)
    return int(math.floor(T * SCALE))


def _eigenvalue_coefficients(n: int) -> tuple[np.ndarray, int]:
    """
    Return integer-scaled coefficient matrix C of shape (J, half) where
    C[j-1, k-1] = int-round(c_jk · SCALE) for j ∈ [1, J], k ∈ [1, half].

    J = ⌊N/2⌋ covers all distinct λ_j (λ_j = λ_{N-j} for circulants).
    """
    half = n // 2
    J = half
    C = np.zeros((J, half), dtype=np.int64)
    even = (n % 2 == 0)
    for j in range(1, J + 1):
        for k in range(1, half + 1):
            if even and k == half:
                val = math.cos(math.pi * j)  # single-term at diameter
            else:
                val = 2.0 * math.cos(2.0 * math.pi * j * k / n)
            C[j - 1, k - 1] = int(round(val * SCALE))
    return C, J


def solve_box(
    n: int,
    d: int,
    alpha_target: int,
    clauses,
    coef_matrix: np.ndarray,
    hint: list[int] | None,
    time_limit: float,
    workers: int,
) -> list[int] | None:
    """Decision: is there a K4-free circulant at degree d with
    Hoffman-certified α ≤ α_target? Returns S_half if SAT, else None."""
    half = n // 2
    model = cp_model.CpModel()
    g = [None] + [model.NewBoolVar(f"g_{k}") for k in range(1, half + 1)]

    # K4-free clauses
    for gaps in clauses:
        model.AddBoolOr([g[k].Not() for k in gaps])

    # Degree
    if n % 2 == 0:
        model.Add(2 * sum(g[k] for k in range(1, half)) + g[half] == d)
    else:
        model.Add(2 * sum(g[k] for k in range(1, half + 1)) == d)

    # Hoffman: for each j, Σ c_jk · g_k ≥ T(α_target)
    T_int = _hoffman_threshold_int(n, d, alpha_target)
    J = coef_matrix.shape[0]
    for j in range(J):
        terms = []
        for k in range(1, half + 1):
            c = int(coef_matrix[j, k - 1])
            if c != 0:
                terms.append(c * g[k])
        if terms:
            model.Add(sum(terms) >= T_int)

    # Warm-start hint
    if hint:
        hint_set = set(hint)
        for k in range(1, half + 1):
            model.AddHint(g[k], 1 if k in hint_set else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return [k for k in range(1, half + 1) if solver.Value(g[k]) == 1]


def warm_start(n: int, max_conn_size: int = 6) -> dict[int, list[int]]:
    """Run CirculantSearchFast and return {degree: best S_half}."""
    try:
        w = CirculantSearchFast(
            n=n, top_k=20, max_conn_size=max_conn_size, min_conn_size=1,
            verbosity=0,
        )
        results = w.run()
    except Exception:
        return {}
    per_d: dict[int, tuple[float, list[int]]] = {}
    for r in results:
        md = r.metadata or {}
        conn = md.get("connection_set")
        if not isinstance(conn, list) or not conn:
            continue
        d = int(r.d_max)
        c = float(r.c_log) if r.c_log is not None else float("inf")
        if d not in per_d or c < per_d[d][0]:
            per_d[d] = (c, [int(x) for x in conn])
    return {d: s for d, (_, s) in per_d.items()}


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


def search_n(
    n: int,
    d_min: int,
    d_max: int | None,
    time_limit: float,
    alpha_time_limit: float,
    workers: int,
) -> tuple[float | None, int, int, list[int], int, float]:
    """Return (best_c, best_alpha, best_d, best_S, n_sat_calls, dt)."""
    t0 = time.monotonic()
    clauses = _k4_gap_clauses(n)
    coef_matrix, _ = _eigenvalue_coefficients(n)
    d_hi = d_max if d_max is not None else min(n - 2, max(6, int(2 * n ** 0.5)))

    # Warm start
    hints = warm_start(n)

    # Initial best from warm start
    best_c = None
    best_S: list[int] = []
    best_d = 0
    best_alpha = 0
    for d, S in hints.items():
        G = _circulant_graph(n, S)
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        alpha, _ = alpha_cpsat(adj, time_limit=alpha_time_limit, vertex_transitive=True)
        if alpha <= 0:
            continue
        c = c_log_value(alpha, n, d)
        if c is None:
            continue
        if best_c is None or c < best_c:
            best_c = c
            best_S = S
            best_d = d
            best_alpha = alpha

    n_sat_calls = 0

    # For each d in range, iterate α_target downward
    for d in range(d_min, d_hi + 1):
        if log(d) <= 0:
            continue

        # Caro-Wei minimum α at this d
        alpha_cw = ceil(n / (d + 1))

        # Max useful α at this d (strict improvement over best_c)
        if best_c is None:
            alpha_max = n - 1
        else:
            # want α * d / (N * ln d) < best_c
            alpha_max = int(math.floor(best_c * n * log(d) / d))
            if alpha_max * d / (n * log(d)) >= best_c:
                alpha_max -= 1  # strict
        if alpha_max < alpha_cw:
            continue  # d can't beat current best

        # Try α_target = alpha_max, alpha_max-1, ..., alpha_cw
        alpha_target = alpha_max
        hint = hints.get(d)
        while alpha_target >= alpha_cw:
            n_sat_calls += 1
            S = solve_box(
                n, d, alpha_target, clauses, coef_matrix,
                hint=hint,
                time_limit=time_limit,
                workers=workers,
            )
            if S is None:
                break  # no Hoffman-certified circulant at this α_target; move to next d
            # Verify with exact α
            G = _circulant_graph(n, S)
            adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
            actual_alpha, _ = alpha_cpsat(
                adj, time_limit=alpha_time_limit, vertex_transitive=True
            )
            if actual_alpha <= 0:
                break
            c = c_log_value(actual_alpha, n, d)
            if c is None:
                break
            if best_c is None or c < best_c:
                best_c = c
                best_S = S
                best_d = d
                best_alpha = actual_alpha
            # Tighten to actual_alpha - 1 (SAT might have given us α << α_target)
            alpha_target = actual_alpha - 1

    dt = time.monotonic() - t0
    return best_c, best_alpha, best_d, best_S, n_sat_calls, dt


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=100)
    ap.add_argument("--d-min", type=int, default=3)
    ap.add_argument("--d-max", type=int, default=None)
    ap.add_argument("--time-limit", type=float, default=15.0, help="per (d, α_target) SAT budget")
    ap.add_argument("--alpha-time-limit", type=float, default=60.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--save", action="store_true")
    args = ap.parse_args()

    store = GraphStore(DEFAULT_GRAPHS) if args.save else None
    summary: list[tuple[int, float | None, int, int, list[int], int, float]] = []

    for n in range(args.n_min, args.n_max + 1):
        best_c, best_alpha, best_d, best_S, n_calls, dt = search_n(
            n=n,
            d_min=args.d_min,
            d_max=args.d_max,
            time_limit=args.time_limit,
            alpha_time_limit=args.alpha_time_limit,
            workers=args.workers,
        )
        summary.append((n, best_c, best_alpha, best_d, best_S, n_calls, dt))
        print(
            f"[sat_optimal n={n:>3}] c={_fmt(best_c)} α={best_alpha} d={best_d} "
            f"S={best_S} calls={n_calls} ({dt:.1f}s)",
            flush=True,
        )
        if args.save and store is not None and best_S:
            G = _circulant_graph(n, best_S)
            store.add_graph(
                G,
                source="sat_circulant_optimal",
                filename="sat_circulant_optimal.json",
                connection_set=best_S,
                degree=best_d,
                method="sat_hoffman_warm",
                n_sat_calls=n_calls,
            )

    print()
    print("=" * 80)
    print(f"{'n':>4}{'best c':>12}{'α':>5}{'d':>5}{'|S|':>5}{'calls':>7}{'t (s)':>10}")
    print("=" * 80)
    for n, c, a, d, S, calls, dt in summary:
        print(f"{n:>4}{_fmt(c):>12}{a:>5}{d:>5}{len(S):>5}{calls:>7}{dt:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
