"""
search/sat_regular.py
======================
Degree-pinned CP-SAT feasibility scan for min-edge K4-free graphs.

Exploits Hajnal's theorem: the α-critical (equivalently, min-|E|)
K4-free graph is near-regular — every vertex has degree D or D+1 for
some integer D. So the scan is: iterate D upward from the Ramsey
floor and solve a pure feasibility model at each D; the first feasible
D is the answer. Edge ranges for consecutive D values don't overlap,
so no optimization objective is needed.

Faster than `SATExact` because the model is smaller (degree pinned,
not bounded) and because it's feasibility-only. But it *assumes* the
optimum is regular — if it isn't (e.g. bugs in the Hajnal reduction,
or α-target outside the regular window), this search can return
INFEASIBLE where an unconstrained solver would find a witness.

Ports the reference `solve_min_edges` logic into the `Search`
framework. Matches its behavior; not optimized further.
"""

from __future__ import annotations

import os
import sys
from itertools import combinations
from math import comb

import networkx as nx
from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import alpha_exact_nx
from utils.ramsey import degree_bounds as _ramsey_degree_bounds

from .base import Search


_LAZY_THRESHOLD = 5_000_000

_STATUS_NAME = {
    cp_model.OPTIMAL:    "FEASIBLE",
    cp_model.FEASIBLE:   "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN:    "TIMEOUT",
}


class SATRegular(Search):
    """
    Degree-pinned CP-SAT scan for the min-edge K4-free graph with α ≤ alpha.

    Constraints
    -----------
    alpha     : int (hard)  — α(G) ≤ alpha. Mandatory.
    timeout_s : float       — total wall budget across all D values. Default 600.
    workers   : int         — CP-SAT num_search_workers. Default os.cpu_count().

    Model at fixed D
    ----------------
    Variables : x_{i,j} for i < j.
    Clauses   :
      * K4-free — every 4-set is missing ≥ 1 edge.
      * Near-regular — D ≤ deg(v) ≤ D+1 for every v.
      * Independence — either directly (C(n, α+1) disjunctions) or via
        lazy cuts when C(n, α+1) exceeds a threshold: each iteration
        solves feasibility, computes α of the witness, and if α>alpha
        adds a "≥1 edge inside this independent set" cut.

    Return
    ------
    Either 0 graphs (INFEASIBLE / TIMEOUT) or 1 graph (the min-edge
    witness at the first feasible D).
    """

    name = "sat_regular"

    def __init__(
        self,
        n: int,
        *,
        alpha: int,
        timeout_s: float = 600.0,
        workers: int | None = None,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        **kwargs,
    ):
        if workers is None:
            workers = os.cpu_count() or 8
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            alpha=alpha,
            timeout_s=timeout_s,
            workers=workers,
            **kwargs,
        )

    # ── Ramsey degree window ─────────────────────────────────────────────────

    def _degree_bounds(self) -> tuple[int, int]:
        d_lo, d_hi = _ramsey_degree_bounds(self.n, self.alpha)
        return (d_lo if d_lo != -1 else 0), (d_hi if d_hi != -1 else self.n - 1)

    # ── model ────────────────────────────────────────────────────────────────

    def _build_model(self, D: int, *, enumerate_alpha: bool, alpha_cuts: list[tuple[int, ...]] | None):
        n = self.n
        model = cp_model.CpModel()

        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in range(n):
            for j in range(i + 1, n):
                x[(i, j)] = model.new_bool_var(f"x_{i}_{j}")

        # K4-free.
        for a, b, c, d in combinations(range(n), 4):
            model.add(
                x[(a, b)] + x[(a, c)] + x[(a, d)]
                + x[(b, c)] + x[(b, d)] + x[(c, d)] <= 5
            )

        # Near-regularity: D ≤ deg(v) ≤ D+1.
        for v in range(n):
            inc = [x[(min(v, j), max(v, j))] for j in range(n) if j != v]
            model.add(sum(inc) >= D)
            model.add(sum(inc) <= D + 1)

        if enumerate_alpha:
            k = self.alpha + 1
            for subset in combinations(range(n), k):
                edges = [x[(i, j)] for i, j in combinations(subset, 2)]
                model.add(sum(edges) >= 1)

        if alpha_cuts:
            for iset in alpha_cuts:
                edges = [
                    x[tuple(sorted((iset[a], iset[b])))]
                    for a in range(len(iset))
                    for b in range(a + 1, len(iset))
                ]
                model.add(sum(edges) >= 1)

        return model, x

    def _solve(self, model, x, time_limit: float):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(time_limit)
        solver.parameters.num_workers = int(self.workers)
        status = solver.solve(model)
        status_name = _STATUS_NAME.get(status, f"STATUS_{status}")
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            G = nx.Graph()
            G.add_nodes_from(range(self.n))
            for (i, j), var in x.items():
                if solver.value(var):
                    G.add_edge(i, j)
            return status_name, G
        return status_name, None

    def _solve_for_D_direct(self, D: int, time_limit: float):
        model, x = self._build_model(D, enumerate_alpha=True, alpha_cuts=None)
        status, G = self._solve(model, x, time_limit)
        return status, G, 0

    def _solve_for_D_lazy(self, D: int, time_limit: float):
        """Feasibility with lazy α cutting planes. Adds one cut per
        violating iteration; caps at 500 iterations."""
        import time
        t0 = time.monotonic()
        alpha_cuts: list[tuple[int, ...]] = []
        for iteration in range(1, 501):
            remaining = time_limit - (time.monotonic() - t0)
            if remaining <= 1:
                return "TIMEOUT", None, iteration
            model, x = self._build_model(D, enumerate_alpha=False, alpha_cuts=alpha_cuts)
            status, G = self._solve(model, x, remaining)
            if G is None:
                return status, None, iteration
            a_actual, iset = alpha_exact_nx(G)
            self._log(
                "lazy_iter", level=2,
                D=D, iteration=iteration,
                alpha=a_actual, edges=G.number_of_edges(),
            )
            if a_actual <= self.alpha:
                return "FEASIBLE", G, iteration
            alpha_cuts.append(tuple(iset))
        return "TIMEOUT", None, 500

    # ── run ──────────────────────────────────────────────────────────────────

    def _run(self) -> list[nx.Graph]:
        import time
        t0 = time.monotonic()
        n = self.n

        d_lo, d_hi = self._degree_bounds()
        k = self.alpha + 1
        direct = (k > n) or (comb(n, k) <= _LAZY_THRESHOLD)
        method = "cpsat_direct" if direct else "cpsat_lazy"

        self._log(
            "scan_start", level=1,
            d_lo=d_lo, d_hi=d_hi, method=method,
        )

        if d_lo > d_hi:
            self._log("scan_end", level=1, status="INFEASIBLE_RAMSEY")
            return []

        for D in range(d_lo, d_hi + 1):
            remaining = self.timeout_s - (time.monotonic() - t0)
            if remaining <= 1:
                self._log("out_of_time", level=1, D=D)
                return []

            D_left = d_hi + 1 - D
            budget = remaining / D_left

            if direct:
                status, G, iters = self._solve_for_D_direct(D, budget)
            else:
                status, G, iters = self._solve_for_D_lazy(D, budget)

            self._log(
                "attempt", level=0,
                D=D, status=status, iterations=iters,
                budget_s=round(budget, 1),
            )

            if status == "FEASIBLE" and G is not None:
                self._stamp(G)
                G.graph["metadata"] = {
                    "D":          D,
                    "alpha_cap":  self.alpha,
                    "method":     method,
                    "iterations": iters,
                }
                return [G]

            if status == "TIMEOUT":
                # A TIMEOUT at D means we can't prove INFEASIBLE there;
                # the next D might still be the real min, but we no
                # longer know the smaller D values were ruled out. Match
                # reference behavior: keep scanning.
                continue

        self._log("scan_end", level=1, status="INFEASIBLE")
        return []
