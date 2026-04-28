"""
search/SAT/sat_joint.py
========================
Joint-minimization CP-SAT solver: optimize λ·α(G) + Δ(G) over K₄-free
graphs on n vertices.

Differences from the naive feasibility solver
---------------------------------------------
- α(G) is encoded as an integer variable A ∈ [0, alpha_max], lower-
  bounded by big-M constraints (one per subset of size ≤ alpha_max).
- Δ(G) is encoded as an integer variable D ∈ [0, n-1], with the
  per-vertex degree sum ≤ D.
- The C2 family (no IS of size alpha_max+1) is kept as a hard cap
  so A is well-defined.
- Objective: minimize  alpha_weight·A + D.

Required kwargs
---------------
alpha_max     : int — hard upper cap on α(G).
alpha_weight  : int — λ in the objective. Default n (so α dominates).
time_limit_s  : float — wall-clock budget.
"""

from __future__ import annotations

import os
import sys
from itertools import combinations

import networkx as nx
from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from search.base import Search


_STATUS_NAME = {
    cp_model.OPTIMAL:    "OPTIMAL",
    cp_model.FEASIBLE:   "FEASIBLE",
    cp_model.INFEASIBLE: "UNSAT",
    cp_model.UNKNOWN:    "TIMED_OUT",
}


class SATJoint(Search):
    name = "sat_joint"

    def __init__(
        self,
        n: int,
        *,
        alpha_max: int,
        alpha_weight: int | None = None,
        time_limit_s: float = 60.0,
        **kwargs,
    ):
        if alpha_weight is None:
            alpha_weight = n
        super().__init__(
            n,
            alpha_max=alpha_max,
            alpha_weight=alpha_weight,
            time_limit_s=time_limit_s,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        n = self.n
        amax = self.alpha_max
        lam = self.alpha_weight

        if n <= 0:
            return []

        m = cp_model.CpModel()

        x = {(i, j): m.NewBoolVar(f"x_{i}_{j}") for i, j in combinations(range(n), 2)}
        e = lambda a, b: x[(a, b)] if a < b else x[(b, a)]

        # (C1) K4-free
        for S in combinations(range(n), 4):
            m.Add(sum(e(a, b) for a, b in combinations(S, 2)) <= 5)

        # Hard cap α(G) ≤ amax  (so A is well-defined inside [0, amax])
        if amax + 1 <= n:
            for T in combinations(range(n), amax + 1):
                m.Add(sum(e(a, b) for a, b in combinations(T, 2)) >= 1)

        # A := α(G), via big-M lower-bound family:
        #   for each subset T of size k ≤ amax,
        #       A + k · Σ_{e ⊂ T} x_e  ≥  k
        #   if T is independent (sum = 0), forces A ≥ k.
        A = m.NewIntVar(0, amax, "alpha")
        for k in range(1, amax + 1):
            for T in combinations(range(n), k):
                m.Add(A + k * sum(e(a, b) for a, b in combinations(T, 2)) >= k)

        # D := Δ(G); per-vertex degree ≤ D
        D = m.NewIntVar(0, n - 1, "d_max")
        for v in range(n):
            m.Add(sum(e(v, u) for u in range(n) if u != v) <= D)

        m.Minimize(lam * A + D)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.time_limit_s)
        status = solver.Solve(m)
        status_name = _STATUS_NAME.get(status, str(status))
        self._log(
            "solve_done",
            status=status_name,
            wall_time_s=round(solver.WallTime(), 4),
            objective=solver.ObjectiveValue() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
            best_bound=solver.BestObjectiveBound() if status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        )

        G = nx.Graph()
        G.add_nodes_from(range(n))
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for (i, j), var in x.items():
                if solver.Value(var) == 1:
                    G.add_edge(i, j)
            self._stamp(G)
            G.graph["metadata"] = {
                "status":       status_name,
                "alpha_max":    amax,
                "alpha_weight": lam,
                "A_solver":     solver.Value(A),
                "D_solver":     solver.Value(D),
                "objective":    solver.ObjectiveValue(),
                "best_bound":   solver.BestObjectiveBound(),
                "wall_time_s":  round(solver.WallTime(), 4),
                "time_limit_s": self.time_limit_s,
            }
        else:
            self._stamp(G)
            G.graph["metadata"] = {
                "status":       status_name,
                "alpha_max":    amax,
                "alpha_weight": lam,
                "wall_time_s":  round(solver.WallTime(), 4),
                "time_limit_s": self.time_limit_s,
            }
        return [G]
