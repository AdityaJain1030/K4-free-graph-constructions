#!/usr/bin/env python3
"""
scripts/run_sat_circulant.py
============================
Sweep SAT circulant feasibility across N. For each (N, d) box with d in
[d_min, d_max], builds a K4-free + degree=d CP-SAT model, solves once
(no CEGAR), computes exact α of any feasible S, and keeps the min-c_log
circulant per N.

This is the "fast" mode — no α-optimization loop. It recovers any
circulant the SAT solver happens to return first for each degree; α
post-computation then ranks them. Expected to match CirculantSearchFast
within the degree band where both are run, with less coverage of large
|S| but wider coverage of d-by-d.

Usage:
    micromamba run -n k4free python scripts/run_sat_circulant.py \
        --n-min 10 --n-max 100 --save
"""

import argparse
import json
import os
import sys
import time
from math import log

import numpy as np
import networkx as nx
from ortools.sat.python import cp_model

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import GraphStore, DEFAULT_GRAPHS
from search.sat_circulant import _k4_gap_clauses, _circulant_graph
from utils.graph_props import alpha_cpsat, c_log_value


def _fmt(x):
    return "—" if x is None else f"{x:.4f}"


class _SolutionCollector(cp_model.CpSolverSolutionCallback):
    def __init__(self, g_vars, half, max_solutions):
        super().__init__()
        self.g_vars = g_vars
        self.half = half
        self.max = max_solutions
        self.solutions: list[list[int]] = []

    def on_solution_callback(self):
        S = [k for k in range(1, self.half + 1) if self.Value(self.g_vars[k]) == 1]
        self.solutions.append(S)
        if len(self.solutions) >= self.max:
            self.StopSearch()


def enumerate_feasible(
    n: int,
    d: int,
    clauses,
    time_limit: float,
    workers: int,
    max_solutions: int,
) -> list[list[int]]:
    """Enumerate up to `max_solutions` distinct K4-free circulants with
    deg=d via CP-SAT's solution callback. Much more efficient than
    multiple solve() calls since the search state is reused."""
    half = n // 2
    model = cp_model.CpModel()
    g = [None] + [model.NewBoolVar(f"g_{k}") for k in range(1, half + 1)]

    for gaps in clauses:
        model.AddBoolOr([g[k].Not() for k in gaps])

    if n % 2 == 0:
        model.Add(2 * sum(g[k] for k in range(1, half)) + g[half] == d)
    else:
        model.Add(2 * sum(g[k] for k in range(1, half + 1)) == d)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 1  # enumerate_all requires seq
    solver.parameters.enumerate_all_solutions = True
    cb = _SolutionCollector(g, half, max_solutions)
    solver.Solve(model, cb)
    return cb.solutions


def sample_circulants(
    n: int,
    d: int,
    clauses,
    time_limit: float,
    workers: int,
    n_samples: int,
    alpha_time_limit: float,
) -> tuple[float, int, list[int]] | None:
    """Enumerate up to n_samples K4-free circulants with deg=d, compute α
    of each, return best (c_log, α, S). None if no feasibility at all."""
    solutions = enumerate_feasible(
        n, d, clauses, time_limit, workers, n_samples
    )
    best = None
    for S in solutions:
        G = _circulant_graph(n, S)
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        alpha, _ = alpha_cpsat(
            adj, time_limit=alpha_time_limit, vertex_transitive=True
        )
        if alpha <= 0:
            continue
        c = c_log_value(alpha, n, d)
        if c is None:
            continue
        if best is None or c < best[0]:
            best = (c, alpha, S)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=100)
    ap.add_argument("--d-min", type=int, default=3)
    ap.add_argument("--d-max", type=int, default=None,
                    help="default: min(N-2, max(6, int(2*sqrt(N))))")
    ap.add_argument("--time-limit", type=float, default=10.0,
                    help="per-degree SAT budget")
    ap.add_argument("--alpha-time-limit", type=float, default=60.0,
                    help="exact α per graph time limit")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--samples-per-d", type=int, default=8,
                    help="how many random-seeded SAT feasibility calls per (N, d)")
    ap.add_argument("--save", action="store_true",
                    help="persist best per-N graph under source='sat_circulant'")
    args = ap.parse_args()

    store = GraphStore(DEFAULT_GRAPHS) if args.save else None
    summary: list[tuple[int, float | None, int, int, list[int], float]] = []

    for n in range(args.n_min, args.n_max + 1):
        t_n = time.monotonic()
        clauses = _k4_gap_clauses(n)
        d_hi = args.d_max if args.d_max is not None else min(n - 2, max(6, int(2 * n**0.5)))

        best = None  # (c_log, d, alpha, S_half)
        per_d_log: list[tuple[int, float | None, int]] = []

        for d in range(args.d_min, d_hi + 1):
            if log(d) <= 0:
                continue
            sampled = sample_circulants(
                n, d, clauses,
                time_limit=args.time_limit,
                workers=args.workers,
                n_samples=args.samples_per_d,
                alpha_time_limit=args.alpha_time_limit,
            )
            if sampled is None:
                per_d_log.append((d, None, 0))
                continue
            c, alpha, S = sampled
            per_d_log.append((d, c, alpha))
            if best is None or (c is not None and c < best[0]):
                best = (c, d, alpha, S)

        dt = time.monotonic() - t_n
        if best is not None:
            c, d, alpha, S = best
            summary.append((n, c, alpha, d, S, dt))
            d_str = " ".join(
                f"d{dd}:{_fmt(cc)}/α{aa}" for dd, cc, aa in per_d_log if cc is not None
            )
            print(
                f"[sat_circulant n={n:>3}] best c={_fmt(c)} α={alpha} d={d} "
                f"S={S} ({dt:.1f}s) | {d_str}",
                flush=True,
            )
            if args.save and store is not None:
                G = _circulant_graph(n, S)
                store.add_graph(
                    G,
                    source="sat_circulant",
                    filename="sat_circulant.json",
                    connection_set=S,
                    degree=d,
                    method="sat_feasibility",
                )
        else:
            summary.append((n, None, 0, 0, [], dt))
            print(f"[sat_circulant n={n:>3}] no feasible ({dt:.1f}s)", flush=True)

    print()
    print("=" * 72)
    print(f"{'n':>4}{'best c':>12}{'alpha':>7}{'d':>5}{'|S|':>5}{'t (s)':>10}")
    print("=" * 72)
    for n, c, a, d, S, dt in summary:
        print(f"{n:>4}{_fmt(c):>12}{a:>7}{d:>5}{len(S):>5}{dt:>10.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
