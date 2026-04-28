"""
search/SAT/sat.py
==================
Naive CP-SAT search for K4-free graphs.

The minimal viable formulation; every constraint maps one-to-one onto
its mathematical definition so correctness is obvious by inspection.

Decision variables
------------------
- x_{i,j} ∈ {0, 1} for every unordered pair i < j (one Boolean per
  potential edge). C(n, 2) variables total.

Constraints
-----------
- K4-free: for every 4-subset S of V, at most 5 of its 6 edges are
  present:  Σ_{e ⊂ S, |e|=2} x_e ≤ 5.   [C(n, 4) clauses]
- α(G) ≤ alpha: for every (alpha+1)-subset T, at least one edge is
  present:  Σ_{e ⊂ T, |e|=2} x_e ≥ 1.   [C(n, alpha+1) clauses]
- Δ(G) ≤ d_max: for every vertex v,
            Σ_{u ≠ v} x_{vu} ≤ d_max.   [n clauses]

Optional pre-solve box pruning (`ramsey_prune`, default True)
-------------------------------------------------------------
Before building the model, reject boxes that no K4-free graph on n
vertices can satisfy via four elementary rules — α=0, d=0, Caro-Wei,
and known upper bounds on R(4, α+1). Each rule is sound (only rejects
provably infeasible boxes), so the resulting UNSAT verdict is exact.

Optional row-0 lex symmetry break (`edge_lex`, default True)
------------------------------------------------------------
Force vertex 0's adjacency row to be non-increasing:
    x[0,1] ≥ x[0,2] ≥ … ≥ x[0,n-1].
Quotients out the S_{n-1} subgroup that permutes vertices 1..n-1.
Sound (every orbit has a labeling with N(0) packed leftward), cheap
(n−2 pure Bool comparisons, no aux vars, no totalizer), and
empirically a 3–100× win at n≤17 — see experiments/SAT/NEXT.md §P2.
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


_STATUS_NAME = {
    cp_model.OPTIMAL:    "SAT",
    cp_model.FEASIBLE:   "SAT",
    cp_model.INFEASIBLE: "UNSAT",
    cp_model.UNKNOWN:    "TIMED_OUT",
}


def _ramsey_prune(n: int, alpha: int, d_max: int) -> tuple[str, str] | None:
    """Return (rule, reason) if box (n, α, d_max) is provably infeasible
    by elementary Ramsey-style arguments, else None."""
    if n <= 0:
        return None
    if alpha < 0 or d_max < 0:
        return ("invalid_input", f"alpha={alpha}, d_max={d_max}")
    if alpha == 0:
        return ("alpha_zero", f"α=0 forbids any vertex (n={n})")
    if d_max == 0 and n > alpha:
        return ("dmax_zero", f"d=0 ⇒ α(G)=n={n} > {alpha}")
    if alpha * (d_max + 1) < n:
        return ("caro_wei",
                f"α·(d+1) = {alpha}·{d_max+1} = {alpha*(d_max+1)} < n = {n}")
    k = alpha + 1
    ub = R4_UB.get(k)
    if ub is not None and n >= ub:
        return ("ramsey_4_k",
                f"n={n} ≥ R(4,{k}) ≤ {ub} ⇒ K4-free forces α ≥ {k}")
    return None


class SAT(Search):
    """
    Naive CP-SAT K4-free graph search (decision, no objective).

    Required kwargs
    ---------------
    alpha   : int — independence-number upper bound, α(G) ≤ alpha.
    d_max   : int — max-degree upper bound, Δ(G) ≤ d_max.

    Optional kwargs
    ---------------
    time_limit_s  : float — per-solve wall-clock budget (default 60 s).
    ramsey_prune  : bool  — apply pre-solve Ramsey box pruning
                            (default True). When the pre-check fires,
                            the solver is skipped and `metadata` carries
                            `pruned_by` / `pruned_reason`.
    edge_lex      : bool  — add row-0 lex symmetry break
                            x[0,1] ≥ x[0,2] ≥ … ≥ x[0,n-1] (default
                            True). Cheap and sound; quotients out
                            S_{n-1}.

    Returns
    -------
    Always [G] (length-1 list). On SAT, G is the witness graph. On
    UNSAT or TIMED_OUT, G is the empty graph on n vertices.
    """

    name = "sat"

    def __init__(
        self,
        n: int,
        *,
        alpha: int,
        d_max: int,
        time_limit_s: float = 60.0,
        ramsey_prune: bool = True,
        edge_lex: bool = True,
        cp_workers: int = 1,
        seed_graph: "nx.Graph | None" = None,
        **kwargs,
    ):
        super().__init__(
            n,
            alpha=alpha,
            d_max=d_max,
            time_limit_s=time_limit_s,
            ramsey_prune=ramsey_prune,
            edge_lex=edge_lex,
            cp_workers=cp_workers,
            seed_graph=seed_graph,
            **kwargs,
        )

    def _run(self) -> list[nx.Graph]:
        n = self.n
        alpha = self.alpha
        d_max = self.d_max

        if n <= 0:
            return []

        if self.ramsey_prune:
            pruned = _ramsey_prune(n, alpha, d_max)
            if pruned is not None:
                rule, reason = pruned
                self._log("ramsey_pruned", rule=rule, reason=reason)
                G = nx.Graph()
                G.add_nodes_from(range(n))
                self._stamp(G)
                G.graph["metadata"] = {
                    "status":         "UNSAT",
                    "alpha_bound":    alpha,
                    "d_max_bound":    d_max,
                    "time_limit_s":   self.time_limit_s,
                    "wall_time_s":    0.0,
                    "pruned_by":      rule,
                    "pruned_reason":  reason,
                }
                return [G]

        model = cp_model.CpModel()

        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for i, j in combinations(range(n), 2):
            x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")

        def edge(a: int, b: int) -> cp_model.IntVar:
            return x[(a, b)] if a < b else x[(b, a)]

        for S in combinations(range(n), 4):
            model.Add(sum(edge(a, b) for a, b in combinations(S, 2)) <= 5)

        if alpha + 1 <= n:
            for T in combinations(range(n), alpha + 1):
                model.Add(sum(edge(a, b) for a, b in combinations(T, 2)) >= 1)

        for v in range(n):
            model.Add(sum(edge(v, u) for u in range(n) if u != v) <= d_max)

        # Row-0 lex symmetry break: vertex 0's adjacency row is non-
        # increasing. Sound under S_{n-1} (permuting vertices 1..n-1),
        # since any graph admits a labeling with N(0) packed leftward.
        if self.edge_lex and n >= 3:
            for j in range(1, n - 1):
                model.Add(x[(0, j)] >= x[(0, j + 1)])

        # Solution hint: bias CP-SAT toward the seed graph's edge set.
        # Pure search bias — no soundness impact. The hint may be
        # infeasible under (alpha, d_max, K4) constraints; CP-SAT will
        # repair from there. Empirically helps when the seed is
        # structurally close to a feasible witness.
        if self.seed_graph is not None and self.seed_graph.number_of_nodes() == n:
            seed_edges = {
                (min(u, v), max(u, v)) for u, v in self.seed_graph.edges()
            }
            for (i, j), var in x.items():
                model.AddHint(var, 1 if (i, j) in seed_edges else 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.time_limit_s)
        if int(self.cp_workers) > 1:
            solver.parameters.num_search_workers = int(self.cp_workers)

        status = solver.Solve(model)
        status_name = _STATUS_NAME.get(status, str(status))
        self._log(
            "solve_done",
            status=status_name,
            wall_time_s=round(solver.WallTime(), 4),
            n_branches=solver.NumBranches(),
            n_conflicts=solver.NumConflicts(),
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
            "alpha_bound":  alpha,
            "d_max_bound":  d_max,
            "time_limit_s": self.time_limit_s,
            "wall_time_s":  round(solver.WallTime(), 4),
        }
        return [G]
