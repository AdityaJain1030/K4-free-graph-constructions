#!/usr/bin/env python3
"""
scripts/verify_sat_circulant_optimal.py
=======================================
Spot-check UNSAT-vs-TIMEOUT for the SAT+Hoffman+warm-start sweep.

For a sample of N, re-runs the (d, α_target) α-ladder with:
  - explicit status logging (SAT / UNSAT / TIMEOUT),
  - 300s time limit per box (vs 20s in the production sweep).

Writes a verification log listing which boxes previously returned "UNSAT"
(actually UNKNOWN/timeout in CP-SAT terms) now flip to SAT, proving the
sweep missed a tighter α.
"""

import argparse
import csv
import math
import os
import sys
import time
from math import ceil, log

import numpy as np
import networkx as nx
from ortools.sat.python import cp_model

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search.sat_circulant import _k4_gap_clauses, _circulant_graph
from scripts.run_sat_circulant_optimal import (
    _eigenvalue_coefficients,
    _hoffman_threshold_int,
    SCALE,
    warm_start,
)
from utils.graph_props import alpha_cpsat, c_log_value


def solve_box_with_status(
    n: int,
    d: int,
    alpha_target: int,
    clauses,
    coef_matrix,
    hint,
    time_limit: float,
    workers: int,
):
    """Return (status_name, S_half_or_None, wallclock_s)."""
    half = n // 2
    model = cp_model.CpModel()
    g = [None] + [model.NewBoolVar(f"g_{k}") for k in range(1, half + 1)]

    for gaps in clauses:
        model.AddBoolOr([g[k].Not() for k in gaps])

    if n % 2 == 0:
        model.Add(2 * sum(g[k] for k in range(1, half)) + g[half] == d)
    else:
        model.Add(2 * sum(g[k] for k in range(1, half + 1)) == d)

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

    if hint:
        hint_set = set(hint)
        for k in range(1, half + 1):
            model.AddHint(g[k], 1 if k in hint_set else 0)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers
    t0 = time.monotonic()
    status = solver.Solve(model)
    dt = time.monotonic() - t0
    name = solver.StatusName(status)

    S = None
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        S = [k for k in range(1, half + 1) if solver.Value(g[k]) == 1]

    return name, S, dt


def verify_n(n: int, writer, time_limit: float, workers: int):
    """Re-run the α-ladder for N with long time limit. Writes per-box rows."""
    clauses = _k4_gap_clauses(n)
    coef_matrix, _ = _eigenvalue_coefficients(n)

    hints = warm_start(n)
    # warm-start gives per-degree S dict plus best c_log
    best_c = None
    for d, S in hints.items():
        G = _circulant_graph(n, S)
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        alpha, _ = alpha_cpsat(adj, time_limit=60, vertex_transitive=True)
        if alpha <= 0:
            continue
        c = c_log_value(alpha, n, d)
        if c is None:
            continue
        if best_c is None or c < best_c:
            best_c = c

    d_hi = min(n - 2, max(6, int(2 * n**0.5)))

    for d in range(3, d_hi + 1):
        if log(d) <= 0:
            continue
        alpha_cw = ceil(n / (d + 1))
        if best_c is None:
            alpha_max = n - 1
        else:
            alpha_max = int(math.floor(best_c * n * log(d) / d))
            if alpha_max * d / (n * log(d)) >= best_c:
                alpha_max -= 1
        if alpha_max < alpha_cw:
            continue

        alpha_target = alpha_max
        hint = hints.get(d)
        while alpha_target >= alpha_cw:
            status_name, S, dt = solve_box_with_status(
                n, d, alpha_target, clauses, coef_matrix,
                hint=hint, time_limit=time_limit, workers=workers,
            )
            row = {
                "n": n,
                "d": d,
                "alpha_target": alpha_target,
                "alpha_cw": alpha_cw,
                "status": status_name,
                "time_s": round(dt, 2),
                "S": ",".join(str(x) for x in (S or [])),
            }
            writer.writerow(row)
            print(
                f"  N={n} d={d} α≤{alpha_target}  status={status_name:<10} "
                f"t={dt:.1f}s  S={S}",
                flush=True,
            )

            if status_name not in ("OPTIMAL", "FEASIBLE"):
                # UNSAT or TIMEOUT — either way, advance to next d.
                break

            # Got SAT. Compute actual α, then tighten.
            G = _circulant_graph(n, S)
            adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
            actual_alpha, _ = alpha_cpsat(
                adj, time_limit=60, vertex_transitive=True
            )
            if actual_alpha <= 0:
                break
            c = c_log_value(actual_alpha, n, d)
            if c is not None and (best_c is None or c < best_c):
                best_c = c
            alpha_target = actual_alpha - 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-list", type=int, nargs="+",
                    default=[43, 62, 71, 86, 97])
    ap.add_argument("--time-limit", type=float, default=300.0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--logfile", default="results/sat_circulant_verify/boxes.csv")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.logfile), exist_ok=True)
    t_all = time.monotonic()

    with open(args.logfile, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["n", "d", "alpha_target", "alpha_cw", "status", "time_s", "S"],
        )
        w.writeheader()

        for n in args.n_list:
            t_n = time.monotonic()
            print(f"\n===== N={n} =====", flush=True)
            verify_n(n, w, args.time_limit, args.workers)
            dt = time.monotonic() - t_n
            print(f"  (N={n} took {dt:.1f}s)", flush=True)

    total = time.monotonic() - t_all
    print(f"\n=== total verification time: {total:.1f}s ({total/60:.1f}min) ===")
    print(f"log: {args.logfile}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
