"""
search/SAT/sat_min_deg.py
==========================
CP-SAT solver for Variant A of the K4-free box problem: fix (n, α),
minimize Δ(G).

Encoding
--------
Decision variables: same x_{i,j} ∈ {0,1} edge indicators as the naive
feasibility model, plus one integer variable D ∈ [D_lo, D_hi]
bounding Δ(G) from above.

Constraints:
- (C1) K4-free                         : Σ_{e⊂S} x_e ≤ 5      (unchanged)
- (C2) α-bound                         : Σ_{e⊂T} x_e ≥ 1      (unchanged)
- (C3') Variable degree bound          : Σ_{u≠v} x_{vu} ≤ D   (one per v)

Objective: min D. At optimum, D = Δ(G*).

Bounds on D
-----------
- D_lo = max(0, ⌈n/α⌉ - 1)  — Caro–Wei floor: any graph with α(G) ≤ α
  satisfies Δ(G) ≥ n/α - 1. Sound to inject as the integer-variable
  lower bound.
- D_hi = n - 1 (default), or caller-supplied tighter cap.

Pre-solve pruning
-----------------
- α = 0, n ≥ 1            → UNSAT
- n ≥ R(4, α+1) UB        → UNSAT (Ramsey wall)
- D_lo > D_hi             → UNSAT (caller asked for impossible cap)
- α + 1 > n               → trivial SAT (empty graph, D = 0)

See `experiments/SAT/MIN_DEG.md` for the full formalism.
"""

from __future__ import annotations

import os
import sys
from itertools import combinations

import networkx as nx
from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from search.base import Search
from utils.ramsey import R4_UB


def _ramsey_prune_no_d(n: int, alpha: int) -> tuple[str, str] | None:
    """Pre-solve box prune for the (n, α) pair. The d-dependent rules
    (Caro-Wei, d=0) are inapplicable here — Caro-Wei is folded into
    D_lo, and d=0 is a special case of D_lo ≥ 1 when α < n."""
    if n <= 0:
        return None
    if alpha < 0:
        return ("invalid_input", f"alpha={alpha}")
    if alpha == 0:
        return ("alpha_zero", f"α=0 forbids any vertex (n={n})")
    k = alpha + 1
    ub = R4_UB.get(k)
    if ub is not None and n >= ub:
        return ("ramsey_4_k",
                f"n={n} ≥ R(4,{k}) ≤ {ub} ⇒ K4-free forces α ≥ {k}")
    return None


class SATMinDeg(Search):
    """
    CP-SAT optimization: at fixed (n, α), find a K4-free graph with
    α(G) ≤ α and minimum Δ(G).

    Required kwargs
    ---------------
    alpha   : int — independence-number upper bound, α(G) ≤ alpha.

    Optional kwargs
    ---------------
    d_lower      : int  — override Caro–Wei floor.
    d_upper      : int  — override n-1 ceiling.
    time_limit_s : float — solver wall-clock budget (default 60 s).
    ramsey_prune : bool — apply pre-solve box prune (default True).
    edge_lex     : bool — row-0 lex symmetry break
                          x[0,1] ≥ x[0,2] ≥ … ≥ x[0,n-1] (default
                          True). See experiments/SAT/NEXT.md §P2.

    Returns
    -------
    Always [G]. On SAT, G is the witness with minimum (proven or not)
    max degree. On UNSAT or TIMED_OUT, G is the empty graph on n
    vertices. Inspect G.graph["metadata"]:
      - status      ∈ {"SAT", "UNSAT", "TIMED_OUT"}
      - optimality  ∈ {"proven", "unverified"} (only on SAT)
      - d_min       = solver's D value at termination
      - d_lower / d_upper / objective / best_bound for diagnostics.
    """

    name = "sat_min_deg"

    def __init__(
        self,
        n: int,
        *,
        alpha: int,
        d_lower: int | None = None,
        d_upper: int | None = None,
        time_limit_s: float = 60.0,
        ramsey_prune: bool = True,
        edge_lex: bool = True,
        **kwargs,
    ):
        super().__init__(
            n,
            alpha=alpha,
            d_lower=d_lower,
            d_upper=d_upper,
            time_limit_s=time_limit_s,
            ramsey_prune=ramsey_prune,
            edge_lex=edge_lex,
            **kwargs,
        )

    def _empty_graph_with_meta(self, **meta) -> nx.Graph:
        G = nx.Graph()
        G.add_nodes_from(range(self.n))
        self._stamp(G)
        G.graph["metadata"] = meta
        return G

    def _run(self) -> list[nx.Graph]:
        n = self.n
        alpha = self.alpha

        if n <= 0:
            return []

        # Caro–Wei floor and ceiling.
        cw_floor = max(0, -(-n // alpha) - 1) if alpha >= 1 else 0
        d_lo = self.d_lower if self.d_lower is not None else cw_floor
        d_hi = self.d_upper if self.d_upper is not None else n - 1

        # ---------- pre-solve pruning ----------
        if self.ramsey_prune:
            pruned = _ramsey_prune_no_d(n, alpha)
            if pruned is not None:
                rule, reason = pruned
                self._log("ramsey_pruned", rule=rule, reason=reason)
                return [self._empty_graph_with_meta(
                    status="UNSAT",
                    alpha_bound=alpha,
                    d_lower=d_lo,
                    d_upper=d_hi,
                    pruned_by=rule,
                    pruned_reason=reason,
                    time_limit_s=self.time_limit_s,
                    wall_time_s=0.0,
                )]

        if d_lo > d_hi:
            self._log("infeasible_d_range", d_lo=d_lo, d_hi=d_hi)
            return [self._empty_graph_with_meta(
                status="UNSAT",
                alpha_bound=alpha,
                d_lower=d_lo,
                d_upper=d_hi,
                pruned_by="d_range_empty",
                pruned_reason=f"d_lower={d_lo} > d_upper={d_hi}",
                time_limit_s=self.time_limit_s,
                wall_time_s=0.0,
            )]

        # Trivial: α+1 > n means (C2) is vacuous; the empty graph is optimal.
        if alpha + 1 > n:
            self._log("trivial_sat_empty_graph", reason="alpha+1 > n")
            G = nx.Graph()
            G.add_nodes_from(range(n))
            self._stamp(G)
            G.graph["metadata"] = {
                "status":       "SAT",
                "optimality":   "proven",
                "alpha_bound":  alpha,
                "d_lower":      d_lo,
                "d_upper":      d_hi,
                "d_min":        0,
                "objective":    0,
                "best_bound":   0,
                "trivial":      True,
                "time_limit_s": self.time_limit_s,
                "wall_time_s":  0.0,
            }
            return [G]

        # ---------- model construction ----------
        model = cp_model.CpModel()

        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for i, j in combinations(range(n), 2):
            x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")

        def edge(a: int, b: int) -> cp_model.IntVar:
            return x[(a, b)] if a < b else x[(b, a)]

        # (C1) K4-free
        for S in combinations(range(n), 4):
            model.Add(sum(edge(a, b) for a, b in combinations(S, 2)) <= 5)

        # (C2) α-bound
        for T in combinations(range(n), alpha + 1):
            model.Add(sum(edge(a, b) for a, b in combinations(T, 2)) >= 1)

        # (C3') variable degree bound
        D = model.NewIntVar(d_lo, d_hi, "D")
        for v in range(n):
            model.Add(sum(edge(v, u) for u in range(n) if u != v) <= D)

        # Row-0 lex symmetry break: vertex 0's adjacency row is non-
        # increasing. Sound under S_{n-1} (permuting vertices 1..n-1),
        # since any graph admits a labeling with N(0) packed leftward.
        if self.edge_lex and n >= 3:
            for j in range(1, n - 1):
                model.Add(x[(0, j)] >= x[(0, j + 1)])

        model.Minimize(D)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.time_limit_s)

        status = solver.Solve(model)

        # ---------- status interpretation ----------
        if status == cp_model.OPTIMAL:
            verdict, optimality = "SAT", "proven"
        elif status == cp_model.FEASIBLE:
            verdict, optimality = "SAT", "unverified"
        elif status == cp_model.INFEASIBLE:
            verdict, optimality = "UNSAT", None
        else:
            verdict, optimality = "TIMED_OUT", None

        wall = round(solver.WallTime(), 4)
        self._log(
            "solve_done",
            status=verdict,
            optimality=optimality,
            wall_time_s=wall,
            n_branches=solver.NumBranches(),
            n_conflicts=solver.NumConflicts(),
        )

        G = nx.Graph()
        G.add_nodes_from(range(n))

        meta: dict = {
            "status":       verdict,
            "alpha_bound":  alpha,
            "d_lower":      d_lo,
            "d_upper":      d_hi,
            "time_limit_s": self.time_limit_s,
            "wall_time_s":  wall,
        }

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for (i, j), var in x.items():
                if solver.Value(var) == 1:
                    G.add_edge(i, j)
            meta.update({
                "optimality": optimality,
                "d_min":      solver.Value(D),
                "objective":  solver.ObjectiveValue(),
                "best_bound": solver.BestObjectiveBound(),
            })

        self._stamp(G)
        G.graph["metadata"] = meta
        return [G]
