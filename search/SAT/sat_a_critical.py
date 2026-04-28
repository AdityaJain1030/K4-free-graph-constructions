"""
search/SAT/sat_a_critical.py
============================
CP-SAT search for K4-free α-critical graphs at fixed (n, alpha, d_max).

A graph G is **α-critical** if α(G \ e) > α(G) for every edge e ∈ E(G).
Equivalently, for every edge {u, v} there exists an independent set
S ⊆ V \ {u, v} of size ≥ α - 1 with no vertex of S adjacent to u or v
in G — then {u, v} ∪ S is independent in G \ {u, v} of size ≥ α + 1.

We encode that "witness IS for each edge" directly with auxiliary
booleans `y[{u,v},w]` and the four conditional constraints:

  y[{u,v},w]  →  x[u,v]                            (witness only when edge present)
  Σ_w y[{u,v},w] ≥ α-1     when x[u,v] = 1          (witness has ≥ α-1 vertices)
  y[{u,v},w]  →  ¬x[u,w]   AND  ¬x[v,w]            (no edge from S to u or v)
  y[{u,v},w1] ∧ y[{u,v},w2] → ¬x[w1,w2]            (S is independent in G)

This is a faithful encoding of the α-critical definition with the
α-cap from the standard model. By Theorem 1 of
`docs/theory/A_CRITICALITY.md` the c_log-minimum at every N ≥ 10 is
attained by some K4-free α-critical graph, so the α-critical class
contains the c_log frontier.

Decision variables
------------------
- x[i,j] ∈ {0,1}, i < j: edge boolean (C(n, 2) total).
- y[(i,j), w] ∈ {0,1}, i < j, w ∈ V \ {i,j}: criticality-witness boolean
  (C(n, 2) * (n - 2) total).

Standard constraints (mirrors search/SAT/sat.py)
------------------------------------------------
- K4-free: every 4-subset has ≤ 5 internal edges.       (C(n, 4) clauses)
- α(G) ≤ alpha: every (alpha+1)-subset has ≥ 1 edge.    (C(n, alpha+1) clauses)
- Δ(G) ≤ d_max: per-vertex linear cap.                  (n clauses)

α-criticality constraints (the new content)
-------------------------------------------
For every pair {u, v} (potential edge) and every w ∈ V \ {u, v}:
  - y → x:                  AddImplication(y_{uvw}, x_{uv})
  - y → ¬x_{u,w}:           AddImplication(y_{uvw}, x_{uw}.Not())
  - y → ¬x_{v,w}:           AddImplication(y_{uvw}, x_{vw}.Not())

For every pair {u, v} and every {w1, w2} ⊆ V \ {u, v}:
  - y_{uvw1} ∧ y_{uvw2} → ¬x_{w1,w2}      (witness IS independence)

For every pair {u, v}:
  - x_{uv} = 1 ⇒ Σ_w y_{uv,w} ≥ alpha-1   (witness size, conditional)

Soundness note
--------------
The encoding requires α(G) = alpha exactly (witness size α - 1 is
hardcoded). If α(G) < alpha for the produced graph, the criticality
witness it produces may be over-sized, but the graph is still α-critical
relative to its own (smaller) α. To pin exactly α(G) = alpha we'd need
an extra "∃ IS of size alpha" constraint, but the existence of any
satisfied witness already implies α(G) ≥ alpha. Combined with the α-cap
that forces α(G) ≤ alpha, every SAT solution satisfies α(G) = alpha.

Optional pre-solve box pruning (`ramsey_prune`, default True)
-------------------------------------------------------------
Same elementary checks as `SAT`: α=0, d=0, Caro-Wei, R(4, α+1).

Optional row-0 lex symmetry break (`edge_lex`, default True)
------------------------------------------------------------
Same as `SAT`: x[0,1] ≥ x[0,2] ≥ … ≥ x[0,n-1]. Sound under S_{n-1}.
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
    """Same Ramsey-style box-prune as `search/SAT/sat.py`. Returns
    (rule, reason) when the box is provably infeasible."""
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


class SATACritical(Search):
    """
    CP-SAT decision search for K4-free α-critical graphs.

    Required kwargs
    ---------------
    alpha   : int — independence-number bound (encoded as α(G) ≤ alpha;
                    α-criticality drives α(G) ≥ alpha, so any SAT
                    witness has α(G) = alpha exactly).
    d_max   : int — max-degree cap, Δ(G) ≤ d_max.

    Optional kwargs
    ---------------
    time_limit_s  : float — per-solve wall-clock (default 60 s).
    ramsey_prune  : bool  — pre-solve Ramsey box-prune (default True).
    edge_lex      : bool  — row-0 lex symmetry break (default True).
    cp_workers    : int   — CP-SAT internal num_search_workers (default 1).
    seed_graph    : nx.Graph | None — solution-hint bias (no soundness impact).

    Returns
    -------
    Always [G] (length-1 list). On SAT, G is the α-critical witness.
    On UNSAT or TIMED_OUT, G is the empty graph on n vertices.
    """

    name = "sat_a_critical"

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

        # Edge variables.
        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for i, j in combinations(range(n), 2):
            x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")

        def edge(a: int, b: int) -> cp_model.IntVar:
            return x[(a, b)] if a < b else x[(b, a)]

        # K4-free: per 4-subset, at least one edge missing.
        for S in combinations(range(n), 4):
            model.Add(sum(edge(a, b) for a, b in combinations(S, 2)) <= 5)

        # α(G) ≤ alpha: per (alpha+1)-subset, at least one edge.
        if alpha + 1 <= n:
            for T in combinations(range(n), alpha + 1):
                model.Add(sum(edge(a, b) for a, b in combinations(T, 2)) >= 1)

        # Δ(G) ≤ d_max: per-vertex degree cap.
        for v in range(n):
            model.Add(sum(edge(v, u) for u in range(n) if u != v) <= d_max)

        # α-critical witness booleans: y[(i,j), w] for w ∉ {i, j}.
        # We allocate for every potential edge — y forces itself off
        # automatically when x_{i,j} = 0 via the y → x implication.
        y: dict[tuple[int, int, int], cp_model.IntVar] = {}
        for i, j in combinations(range(n), 2):
            for w in range(n):
                if w == i or w == j:
                    continue
                y[(i, j, w)] = model.NewBoolVar(f"y_{i}_{j}_{w}")

        # (a) y_{ij,w} → x_{i,j}
        for (i, j, w), yvar in y.items():
            model.AddImplication(yvar, x[(i, j)])

        # (b) y_{ij,w} → ¬x_{i,w}  AND  y_{ij,w} → ¬x_{j,w}
        # (no vertex of the witness IS is adjacent to either endpoint)
        for (i, j, w), yvar in y.items():
            model.AddImplication(yvar, edge(i, w).Not())
            model.AddImplication(yvar, edge(j, w).Not())

        # (c) Witness IS independence: y_{ij,w1} ∧ y_{ij,w2} → ¬x_{w1,w2}
        for i, j in combinations(range(n), 2):
            others = [w for w in range(n) if w != i and w != j]
            for w1, w2 in combinations(others, 2):
                model.AddBoolOr([
                    y[(i, j, w1)].Not(),
                    y[(i, j, w2)].Not(),
                    edge(w1, w2).Not(),
                ])

        # (d) Witness size: x_{i,j} = 1 ⇒ Σ_w y_{ij,w} ≥ alpha - 1.
        # (At alpha = 1 the requirement is Σ ≥ 0, vacuous; we still emit
        # to keep the model self-documenting.)
        for i, j in combinations(range(n), 2):
            others = [w for w in range(n) if w != i and w != j]
            model.Add(
                sum(y[(i, j, w)] for w in others) >= alpha - 1
            ).OnlyEnforceIf(x[(i, j)])

        # Row-0 lex symmetry break: vertex 0's adjacency row is non-
        # increasing. Sound under S_{n-1}.
        if self.edge_lex and n >= 3:
            for j in range(1, n - 1):
                model.Add(x[(0, j)] >= x[(0, j + 1)])

        # Optional solution hint.
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
            "a_critical":   True,
        }
        return [G]
