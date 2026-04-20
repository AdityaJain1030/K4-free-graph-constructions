"""
search/sat_regular.py
======================
Degree-banded CP-SAT scan for min-edge K4-free graphs.

At each `D`, constrains `D ≤ deg(v) ≤ D + degree_spread` and solves a
two-phase scheme:

  Phase 1  cheap feasibility check at D (tight budget). If
           INFEASIBLE, move to D+1. If TIMEOUT, heuristically move on.
           If FEASIBLE, the witness is carried into phase 2.

  Phase 2  (only when `minimize_edges=True`) warm-starts CP-SAT's
           edge-count minimization with the phase-1 witness as a hint
           and `sum(x) ≤ |E_feas|-1` as a tightening bound. Gets the
           bulk of the remaining time budget.

Inherits every accelerator that won the `sat_exact` laptop sweep:
bool-or clauses for K4-free + α, `edge_lex` row-0 symmetry, row-0
decision branching, and the `hard_box_params` CP-SAT dial.

See `docs/searches/sat/SAT_REGULAR.md`.
"""

from __future__ import annotations

import os
import sys
import time
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
    cp_model.OPTIMAL:    "OPTIMAL",
    cp_model.FEASIBLE:   "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN:    "TIMEOUT",
}

_SYMMETRY_MODES = ("none", "anchor", "chain", "edge_lex")

# Budget allocation knobs.
_FEAS_BUDGET_FRAC = 0.15   # phase-1 gets at most this fraction of remaining
_FEAS_BUDGET_MAX  = 90.0   # ... or this many seconds, whichever smaller
_FEAS_BUDGET_MIN  = 5.0    # floor so phase-1 always has room to prove small cases


class SATRegular(Search):
    """
    Two-phase CP-SAT scan for the min-edge K4-free graph with α ≤ alpha.

    Constraints
    -----------
    alpha          : int (hard) — α(G) ≤ alpha. Mandatory.
    degree_spread  : int        — `D ≤ deg(v) ≤ D + degree_spread`.
                                  0 = D-regular. 1 = Hajnal near-regular.
                                  ≥2 = relaxes Hajnal; reaches true optima
                                  whose optimal deg sequence spans >2 values.
                                  Default 1.
    timeout_s      : float      — wall budget for the whole (n, α) run.
    workers        : int        — CP-SAT workers. Default os.cpu_count().

    Solve strategy
    --------------
    minimize_edges : bool. Add `minimize Σx` objective, warm-started
        from the phase-1 feasibility witness. Cost: slower; gain:
        certified min-edge at the returned D. Default False.

    Accelerators (all defaults carried over from sat_exact)
    -------------------------------------------------------
    symmetry_mode   : "edge_lex" (default) | "anchor" | "chain" | "none".
    branch_on_v0    : bool. CP-SAT decision strategy on row 0.
        Default True.
    hard_box_params : bool. linearization_level=2, probing_level=3,
        symmetry_level=4. Default True when `minimize_edges`, else False
        (heavy presolve is wasted on easy feasibility checks).
    random_seed     : int | None. Forwarded to CP-SAT.

    Return
    ------
    0 graphs (INFEASIBLE / TIMEOUT) or 1 graph (witness at first
    feasible D; minimized when `minimize_edges`).
    """

    name = "sat_regular"

    def __init__(
        self,
        n: int,
        *,
        alpha: int,
        timeout_s: float = 600.0,
        workers: int | None = None,
        degree_spread: int = 1,
        symmetry_mode: str = "edge_lex",
        branch_on_v0: bool = True,
        hard_box_params: bool | None = None,
        minimize_edges: bool = False,
        random_seed: int | None = None,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        **kwargs,
    ):
        if workers is None:
            workers = os.cpu_count() or 8
        if degree_spread < 0:
            raise ValueError(f"degree_spread must be ≥ 0; got {degree_spread}")
        if symmetry_mode not in _SYMMETRY_MODES:
            raise ValueError(
                f"symmetry_mode={symmetry_mode!r} not in {_SYMMETRY_MODES}"
            )
        # Hard box params default: on for minimize, off for pure feasibility.
        if hard_box_params is None:
            hard_box_params = bool(minimize_edges)
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            alpha=alpha,
            timeout_s=timeout_s,
            workers=workers,
            degree_spread=degree_spread,
            symmetry_mode=symmetry_mode,
            branch_on_v0=branch_on_v0,
            hard_box_params=hard_box_params,
            minimize_edges=minimize_edges,
            random_seed=random_seed,
            **kwargs,
        )

    # ── Ramsey degree window ─────────────────────────────────────────────────

    def _degree_bounds(self) -> tuple[int, int]:
        d_lo, d_hi = _ramsey_degree_bounds(self.n, self.alpha)
        return (d_lo if d_lo != -1 else 0), (d_hi if d_hi != -1 else self.n - 1)

    # ── model ────────────────────────────────────────────────────────────────

    def _build_model(
        self,
        D: int,
        *,
        enumerate_alpha: bool,
        alpha_cuts: list[tuple[int, ...]] | None,
        minimize: bool,
        edge_ub: int | None = None,
        hint: "nx.Graph | None" = None,
    ):
        """Build the CP-SAT model at fixed D.

        `minimize`: add `minimize Σx` objective.
        `edge_ub`: if set, add `Σx ≤ edge_ub` (tightens feasibility bound).
        `hint`: if set, pass its adjacency as CP-SAT search hints.
        """
        n = self.n
        model = cp_model.CpModel()

        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in range(n):
            for j in range(i + 1, n):
                x[(i, j)] = model.new_bool_var(f"x_{i}_{j}")

        # K4-free: one 6-literal bool-or of negated edges per 4-set.
        for a, b, c, d in combinations(range(n), 4):
            model.add_bool_or([
                x[(a, b)].negated(), x[(a, c)].negated(), x[(a, d)].negated(),
                x[(b, c)].negated(), x[(b, d)].negated(), x[(c, d)].negated(),
            ])

        def deg_expr(v):
            return sum(x[(min(v, u), max(v, u))] for u in range(n) if u != v)

        # Degree band: D ≤ deg(v) ≤ D + spread.
        d_hi_vertex = D + self.degree_spread
        for v in range(n):
            model.add(deg_expr(v) >= D)
            model.add(deg_expr(v) <= d_hi_vertex)

        # Independence: (α+1)-subsets each contain ≥1 edge.
        if enumerate_alpha:
            k = self.alpha + 1
            if k <= n:
                for subset in combinations(range(n), k):
                    edges = [x[(i, j)] for i, j in combinations(subset, 2)]
                    model.add_bool_or(edges)

        if alpha_cuts:
            for iset in alpha_cuts:
                edges = [
                    x[tuple(sorted((iset[a], iset[b])))]
                    for a in range(len(iset))
                    for b in range(a + 1, len(iset))
                ]
                model.add_bool_or(edges)

        # Symmetry break.
        if self.symmetry_mode == "chain":
            for i in range(n - 1):
                model.add(deg_expr(i) >= deg_expr(i + 1))
        elif self.symmetry_mode == "anchor":
            for v in range(1, n):
                model.add(deg_expr(0) >= deg_expr(v))
        elif self.symmetry_mode == "edge_lex":
            # Lex-leader on rows 0..3 (same as sat_exact).
            k_max = 3
            for j in range(1, n - 1):
                k_end = min(k_max, j - 1)
                lhs = sum((1 << (k_end - i)) * x[(i, j)]     for i in range(k_end + 1))
                rhs = sum((1 << (k_end - i)) * x[(i, j + 1)] for i in range(k_end + 1))
                model.add(lhs >= rhs)

        # Branch on row 0 (pairs with edge_lex).
        if self.branch_on_v0:
            row0 = [x[(0, j)] for j in range(1, n)]
            model.add_decision_strategy(
                row0, cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE
            )

        # Tightening upper bound on |E|.
        if edge_ub is not None:
            model.add(sum(x.values()) <= edge_ub)

        # Warm-start hint.
        if hint is not None:
            for i in range(n):
                for j in range(i + 1, n):
                    model.add_hint(x[(i, j)], 1 if hint.has_edge(i, j) else 0)

        if minimize:
            model.minimize(sum(x.values()))

        return model, x

    def _solve_model(self, model, x, time_limit: float, hard_params: bool):
        """Run CP-SAT and extract the graph (if any)."""
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(1.0, float(time_limit))
        solver.parameters.num_workers = int(self.workers)
        if hard_params:
            solver.parameters.linearization_level = 2
            solver.parameters.cp_model_probing_level = 3
            solver.parameters.symmetry_level = 4
            solver.parameters.cp_model_presolve = True
        if self.random_seed is not None:
            solver.parameters.random_seed = int(self.random_seed)

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

    # ── two-phase per-D solve ───────────────────────────────────────────────

    def _phase1_feasibility(self, D: int, time_limit: float, direct: bool):
        """Cheap feasibility solve: no objective, no hard params."""
        if direct:
            model, x = self._build_model(
                D, enumerate_alpha=True, alpha_cuts=None,
                minimize=False,
            )
            status, G = self._solve_model(model, x, time_limit, hard_params=False)
            return status, G, 0
        return self._lazy_alpha_feasibility(D, time_limit)

    def _lazy_alpha_feasibility(self, D: int, time_limit: float):
        """Lazy α-cut feasibility (unchanged semantics from original solver)."""
        t0 = time.monotonic()
        alpha_cuts: list[tuple[int, ...]] = []
        for iteration in range(1, 501):
            remaining = time_limit - (time.monotonic() - t0)
            if remaining <= 1:
                return "TIMEOUT", None, iteration
            model, x = self._build_model(
                D, enumerate_alpha=False, alpha_cuts=alpha_cuts,
                minimize=False,
            )
            status, G = self._solve_model(model, x, remaining, hard_params=False)
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

    def _phase2_minimize(
        self, D: int, time_limit: float, direct: bool, seed: nx.Graph
    ) -> nx.Graph:
        """Minimize edges at D, warm-started by `seed`. Returns the best
        witness found (seed if solver can't improve or times out)."""
        if time_limit <= 2.0:
            return seed
        best = seed
        if direct:
            model, x = self._build_model(
                D, enumerate_alpha=True, alpha_cuts=None,
                minimize=True,
                edge_ub=seed.number_of_edges(),
                hint=seed,
            )
            status, G = self._solve_model(
                model, x, time_limit, hard_params=self.hard_box_params
            )
            if G is not None and G.number_of_edges() <= best.number_of_edges():
                best = G
            return best
        # Lazy-α minimize: iterate cut-add + minimize until α is valid.
        # Practically rare (only kicks in at very large n, α).
        t0 = time.monotonic()
        alpha_cuts: list[tuple[int, ...]] = []
        while True:
            remaining = time_limit - (time.monotonic() - t0)
            if remaining <= 2:
                break
            model, x = self._build_model(
                D, enumerate_alpha=False, alpha_cuts=alpha_cuts,
                minimize=True,
                edge_ub=best.number_of_edges(),
                hint=best,
            )
            status, G = self._solve_model(
                model, x, remaining, hard_params=self.hard_box_params
            )
            if G is None:
                break
            a_actual, iset = alpha_exact_nx(G)
            if a_actual <= self.alpha:
                if G.number_of_edges() <= best.number_of_edges():
                    best = G
                break
            alpha_cuts.append(tuple(iset))
        return best

    # ── run ──────────────────────────────────────────────────────────────────

    def _run(self) -> list[nx.Graph]:
        t0 = time.monotonic()
        n = self.n

        d_lo, d_hi = self._degree_bounds()
        k = self.alpha + 1
        direct = (k > n) or (comb(n, k) <= _LAZY_THRESHOLD)
        method = "cpsat_direct" if direct else "cpsat_lazy"

        self._log(
            "scan_start", level=1,
            d_lo=d_lo, d_hi=d_hi, method=method,
            degree_spread=self.degree_spread,
            symmetry_mode=self.symmetry_mode,
            minimize_edges=self.minimize_edges,
        )

        if d_lo > d_hi:
            self._log("scan_end", level=1, status="INFEASIBLE_RAMSEY")
            return []

        feasibility_witness: nx.Graph | None = None
        feasibility_D: int | None = None
        phase1_iters = 0

        # Phase 1: scan D, each with a cheap feasibility check.
        for D in range(d_lo, d_hi + 1):
            elapsed = time.monotonic() - t0
            remaining = self.timeout_s - elapsed
            if remaining <= 1:
                self._log("out_of_time", level=1, D=D)
                break

            # Cheap infeasibility cap: <= 15% of remaining, capped at 90s.
            feas_budget = min(
                max(_FEAS_BUDGET_MIN, remaining * _FEAS_BUDGET_FRAC),
                _FEAS_BUDGET_MAX,
            )
            status, G, iters = self._phase1_feasibility(D, feas_budget, direct)
            self._log(
                "phase1", level=0,
                D=D, status=status, iterations=iters,
                budget_s=round(feas_budget, 1),
            )
            if G is not None:
                feasibility_witness = G
                feasibility_D = D
                phase1_iters = iters
                break
            # INFEASIBLE or TIMEOUT: next D. (Below true-min D this is
            # usually INFEASIBLE fast; at boundary could be TIMEOUT.)

        if feasibility_witness is None:
            self._log("scan_end", level=1, status="INFEASIBLE")
            return []

        # Phase 2: optional min-edge optimization at the feasible D.
        G = feasibility_witness
        if self.minimize_edges:
            remaining = self.timeout_s - (time.monotonic() - t0)
            feas_e = feasibility_witness.number_of_edges()
            G = self._phase2_minimize(feasibility_D, remaining, direct, feasibility_witness)
            self._log(
                "phase2", level=0,
                D=feasibility_D,
                edges_feas=feas_e,
                edges_final=G.number_of_edges(),
                budget_s=round(remaining, 1),
            )

        self._stamp(G)
        G.graph["metadata"] = {
            "D":              feasibility_D,
            "alpha_cap":      self.alpha,
            "degree_spread":  self.degree_spread,
            "method":         method,
            "iterations":     phase1_iters,
            "symmetry_mode":  self.symmetry_mode,
            "minimize_edges": self.minimize_edges,
        }
        return [G]
