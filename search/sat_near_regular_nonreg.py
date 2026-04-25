"""
search/sat_near_regular_nonreg.py
==================================
CP-SAT enumerator for **non-regular near-regular** K4-free graphs.

Sibling of `sat_regular` but with one extra constraint: at least one
vertex at degree D and at least one vertex at degree D+1. This
eliminates every d-regular graph — and therefore every Cayley /
circulant graph — from the feasible region, since Cayley graphs are
forced to be d-regular by construction.

Rather than returning a single witness, this solver **enumerates up to
`max_iso_per_D` isomorphism classes** per feasible D, using iterative
blocking-clause resolves. Iso-dedup is via nauty's canonical sparse6
(`utils.nauty.canonical_id`).

Why this exists
---------------
Our Cayley/circulant frontier is near-saturated (see the GAP-Cayley
sweep memory + `docs/searches/CAYLEY_TABU_GAP.md`). The n=14, n=15,
n=23 sat_exact winners sit just outside that frontier with degree
sequences {6,5}, {7,6}, {4,3} — textbook near-regular but *not*
regular, hence not reachable from any Cayley-space tabu search.

If such graphs exist at other (n, α), this solver will find them
directly — no α-scan, no d_max-scan, no symmetry via connection-set
assumptions. Every graph it returns is guaranteed non-regular and
therefore non-Cayley.

See `docs/searches/sat/SAT_NEAR_REGULAR_NONREG.md`.
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
from utils.nauty import canonical_id
from utils.ramsey import degree_bounds as _ramsey_degree_bounds

from .base import Search


_LAZY_THRESHOLD = 5_000_000

_STATUS_NAME = {
    cp_model.OPTIMAL:    "OPTIMAL",
    cp_model.FEASIBLE:   "FEASIBLE",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.UNKNOWN:    "TIMEOUT",
}

_SYMMETRY_MODES = ("none", "chain", "edge_lex", "chain+edge_lex")


class SATNearRegularNonReg(Search):
    """
    Enumerate K4-free near-regular NON-regular graphs at fixed (n, α).

    Hard constraints per returned graph
    -----------------------------------
    alpha            : α(G) ≤ alpha.
    near_regular     : deg(v) ∈ {D, D+1} for every v.
    non_regular      : ≥1 vertex of degree D AND ≥1 of degree D+1.
                       (Kills every d-regular solution, which includes
                        every Cayley / circulant graph.)

    Iteration strategy
    ------------------
    For each D in a scan range, repeatedly solve-and-block:
      1. Solve feasibility.
      2. If no solution, stop this D.
      3. Canonicalize; if this iso class is new, emit it.
      4. Add a blocking clause forbidding this *labeled* solution.
      5. Loop until max_iso_per_D unique iso classes OR
         max_labeled_per_D labeled solutions OR
         per-D timeout.

    Kwargs
    ------
    alpha             : int (required) — α cap.
    D                 : int | None — if set, run at exactly this D.
                        Otherwise scan from Ramsey floor.
    scan_mode         : "first" (default) | "all" | "k_after_first".
                        "first": stop after the first D that yields any
                                 solution (min-edge region — best c_log).
                        "all":   scan [d_lo, d_hi] exhaustively.
                        "k_after_first": first D + k more.
    scan_extra_D      : int — k for "k_after_first". Default 0.
    max_iso_per_D     : int — cap on unique iso classes per D. Default 20.
    max_labeled_per_D : int — cap on labeled solver iterations per D.
                        Protects against pathological iso-orbit size.
                        Default 200.
    per_D_timeout_s   : float — per-D wall cap. Default timeout_s / 4.
    timeout_s         : float — total wall cap. Default 900.
    workers           : int — CP-SAT workers. Default os.cpu_count().
    symmetry_mode     : {"none", "chain", "edge_lex", "chain+edge_lex"}.
                        Default "chain" — the chain constraint
                        deg(0) ≥ deg(1) ≥ ... canonicalises the
                        D-vs-(D+1) partition and cuts iso-orbit size
                        without over-constraining. "edge_lex" alone
                        tends to interact oddly with near-regular
                        (see sat_regular's edge_lex commentary) so
                        default is just "chain".
    random_seed       : int | None — CP-SAT random seed.
    branch_on_v0      : bool — CHOOSE_FIRST / SELECT_MAX_VALUE on row 0.

    Returns
    -------
    Up to `max_iso_per_D * scan_breadth` graphs, each carrying metadata:
        D, alpha_cap, iso_canonical_id, solution_rank, method,
        scan_mode, symmetry_mode
    """

    name = "sat_near_regular_nonreg"

    def __init__(
        self,
        n: int,
        *,
        alpha: int,
        D: int | None = None,
        scan_mode: str = "first",
        scan_extra_D: int = 0,
        max_iso_per_D: int = 20,
        max_labeled_per_D: int = 200,
        per_D_timeout_s: float | None = None,
        timeout_s: float = 900.0,
        workers: int | None = None,
        symmetry_mode: str = "chain",
        branch_on_v0: bool = True,
        random_seed: int | None = None,
        top_k: int = 200,
        verbosity: int = 0,
        parent_logger=None,
        **kwargs,
    ):
        if workers is None:
            workers = os.cpu_count() or 8
        if symmetry_mode not in _SYMMETRY_MODES:
            raise ValueError(
                f"symmetry_mode={symmetry_mode!r} not in {_SYMMETRY_MODES}"
            )
        if scan_mode not in ("first", "all", "k_after_first"):
            raise ValueError(f"unknown scan_mode {scan_mode!r}")
        if per_D_timeout_s is None:
            per_D_timeout_s = max(60.0, timeout_s / 4.0)
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            alpha=alpha,
            D=D,
            scan_mode=scan_mode,
            scan_extra_D=scan_extra_D,
            max_iso_per_D=max_iso_per_D,
            max_labeled_per_D=max_labeled_per_D,
            per_D_timeout_s=per_D_timeout_s,
            timeout_s=timeout_s,
            workers=workers,
            symmetry_mode=symmetry_mode,
            branch_on_v0=branch_on_v0,
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
        block_edge_sets: list[frozenset[tuple[int, int]]] | None,
    ):
        """
        Build the CP-SAT model at fixed D with:
          - K4-free,
          - deg ∈ {D, D+1},
          - ≥1 vertex of each degree,
          - α ≤ alpha (direct or lazy),
          - optional blocking clauses for already-enumerated labeled solutions.
        """
        n = self.n
        model = cp_model.CpModel()

        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in range(n):
            for j in range(i + 1, n):
                x[(i, j)] = model.new_bool_var(f"x_{i}_{j}")
        all_pairs = list(x.keys())

        # K4-free
        for a, b, c, d in combinations(range(n), 4):
            model.add_bool_or([
                x[(a, b)].negated(), x[(a, c)].negated(), x[(a, d)].negated(),
                x[(b, c)].negated(), x[(b, d)].negated(), x[(c, d)].negated(),
            ])

        def deg_expr(v):
            return sum(x[(min(v, u), max(v, u))] for u in range(n) if u != v)

        # Near-regular with deg(v) = D + y[v], y[v] ∈ {0,1}
        y = [model.new_bool_var(f"y_{v}") for v in range(n)]
        for v in range(n):
            model.add(deg_expr(v) == D + y[v])

        # Non-regular: at least one y=0 and one y=1
        model.add(sum(y) >= 1)
        model.add(sum(y) <= n - 1)

        # Independence: direct
        if enumerate_alpha:
            k = self.alpha + 1
            if k <= n:
                for subset in combinations(range(n), k):
                    edges = [x[(i, j)] for i, j in combinations(subset, 2)]
                    model.add_bool_or(edges)

        # Independence: lazy cuts
        if alpha_cuts:
            for iset in alpha_cuts:
                edges = [
                    x[tuple(sorted((iset[a], iset[b])))]
                    for a in range(len(iset))
                    for b in range(a + 1, len(iset))
                ]
                model.add_bool_or(edges)

        # Symmetry break: chain (sorted degrees) and/or edge_lex row-0
        if self.symmetry_mode in ("chain", "chain+edge_lex"):
            # deg_expr(i) >= deg_expr(i+1). With near-regular this places
            # all deg-(D+1) vertices before all deg-D vertices.
            for i in range(n - 1):
                model.add(y[i] >= y[i + 1])
        if self.symmetry_mode in ("edge_lex", "chain+edge_lex"):
            for j in range(1, n - 1):
                model.add(x[(0, j)] >= x[(0, j + 1)])

        # Branch on row 0
        if self.branch_on_v0:
            row0 = [x[(0, j)] for j in range(1, n)]
            model.add_decision_strategy(
                row0, cp_model.CHOOSE_FIRST, cp_model.SELECT_MAX_VALUE
            )

        # Blocking clauses: for every already-enumerated labeled solution
        # E_k, at least one edge must flip.
        if block_edge_sets:
            for E_k in block_edge_sets:
                clause = []
                for (i, j) in all_pairs:
                    if (i, j) in E_k:
                        clause.append(x[(i, j)].negated())
                    else:
                        clause.append(x[(i, j)])
                model.add_bool_or(clause)

        return model, x

    def _solve_model(self, model, x, time_limit: float):
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(1.0, float(time_limit))
        solver.parameters.num_workers = int(self.workers)
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

    # ── per-D enumeration ────────────────────────────────────────────────────

    def _enumerate_at_D(
        self,
        D: int,
        budget_s: float,
        direct: bool,
    ) -> list[tuple[str, nx.Graph, int]]:
        """
        Enumerate up to max_iso_per_D iso classes at fixed D.
        Returns list of (iso_canonical_id, graph, solution_rank).
        """
        t0 = time.monotonic()
        iso_found: dict[str, nx.Graph] = {}
        iso_order: list[str] = []
        block_edge_sets: list[frozenset[tuple[int, int]]] = []
        alpha_cuts: list[tuple[int, ...]] = []
        labeled_count = 0

        # Per-labeled-iteration budget: split remaining evenly across
        # expected labeled solutions. Cap to avoid spending 90% on one.
        def _remaining():
            return budget_s - (time.monotonic() - t0)

        while True:
            if len(iso_found) >= self.max_iso_per_D:
                break
            if labeled_count >= self.max_labeled_per_D:
                break
            rem = _remaining()
            if rem < 2.0:
                break
            # Per-iter budget: scale down as we accumulate; min 3s, max 60s.
            iter_budget = max(3.0, min(60.0, rem / 4.0))

            model, x = self._build_model(
                D,
                enumerate_alpha=direct,
                alpha_cuts=None if direct else alpha_cuts,
                block_edge_sets=block_edge_sets,
            )
            status, G = self._solve_model(model, x, iter_budget)
            labeled_count += 1

            if G is None:
                self._log(
                    "enum_terminal", level=1,
                    D=D, status=status, labeled=labeled_count,
                    iso=len(iso_found),
                )
                break

            # Lazy α validation
            if not direct:
                a_actual, iset = alpha_exact_nx(G)
                if a_actual > self.alpha:
                    alpha_cuts.append(tuple(iset))
                    # NOT a valid solution — don't record, don't block
                    # the labeled edges (same α cut takes care of it).
                    self._log(
                        "lazy_cut", level=2,
                        D=D, alpha=a_actual, cut_size=len(iset),
                    )
                    continue

            # Block this labeled solution regardless of iso dedup outcome
            E_k = frozenset((i, j) for (i, j) in G.edges())
            block_edge_sets.append(E_k)

            # Iso dedup
            canon, _ = canonical_id(G)
            if canon not in iso_found:
                iso_found[canon] = G
                iso_order.append(canon)
                self._log(
                    "iso_new", level=1,
                    D=D, iso_rank=len(iso_found),
                    iso_id=canon[:12],
                    edges=G.number_of_edges(),
                    labeled=labeled_count,
                )
            else:
                self._log(
                    "iso_dup", level=2,
                    D=D, iso_id=canon[:12], labeled=labeled_count,
                )

        return [(c, iso_found[c], rank + 1) for rank, c in enumerate(iso_order)]

    # ── run ──────────────────────────────────────────────────────────────────

    def _run(self) -> list[nx.Graph]:
        t0 = time.monotonic()
        n = self.n

        d_lo, d_hi = self._degree_bounds()
        if self.D is not None:
            d_lo = d_hi = int(self.D)

        k = self.alpha + 1
        direct = (k > n) or (comb(n, k) <= _LAZY_THRESHOLD)
        method = "cpsat_direct" if direct else "cpsat_lazy"

        self._log(
            "scan_start", level=1,
            d_lo=d_lo, d_hi=d_hi, method=method,
            max_iso_per_D=self.max_iso_per_D,
            scan_mode=self.scan_mode,
            symmetry_mode=self.symmetry_mode,
        )

        if d_lo > d_hi:
            self._log("scan_end", level=1, status="INFEASIBLE_RAMSEY")
            return []

        all_graphs: list[nx.Graph] = []
        first_feasible_D: int | None = None
        extra_left = self.scan_extra_D

        for D in range(d_lo, d_hi + 1):
            elapsed_total = time.monotonic() - t0
            if elapsed_total >= self.timeout_s:
                self._log("out_of_time", level=1, D=D)
                break
            budget_this_D = min(self.per_D_timeout_s, self.timeout_s - elapsed_total)
            if budget_this_D < 2.0:
                break

            iso_results = self._enumerate_at_D(D, budget_this_D, direct)

            self._log(
                "d_done", level=0,
                D=D, iso_count=len(iso_results),
                elapsed_s=round(time.monotonic() - t0, 2),
            )

            for canon, G, rank in iso_results:
                self._stamp(G)
                G.graph["metadata"] = {
                    "D":                D,
                    "alpha_cap":        self.alpha,
                    "iso_canonical_id": canon,
                    "solution_rank":    rank,
                    "method":           method,
                    "scan_mode":        self.scan_mode,
                    "symmetry_mode":    self.symmetry_mode,
                }
                all_graphs.append(G)

            if iso_results:
                if first_feasible_D is None:
                    first_feasible_D = D
                if self.scan_mode == "first":
                    break
                if self.scan_mode == "k_after_first":
                    if first_feasible_D is not None:
                        if extra_left <= 0 and D > first_feasible_D:
                            break
                        if D > first_feasible_D:
                            extra_left -= 1

        self._log(
            "scan_end", level=1,
            status="ok" if all_graphs else "NO_SOLUTIONS",
            graphs=len(all_graphs),
            first_feasible_D=first_feasible_D,
        )
        return all_graphs
