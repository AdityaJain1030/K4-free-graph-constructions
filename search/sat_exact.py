"""
search/sat_exact.py
=====================
CP-SAT certified K4-free graph search. Exact — every returned graph is
K4-verified by the base class; every INFEASIBLE verdict is a proof
within the per-box time limit.

Every accelerator here is an opt-in flag so we can ablate it. Defaults
are the set that won the laptop sweep at N=10..15 (see
`scripts/ablate_sat_exact.py` for the ablation harness and raw numbers
in `logs/sat_exact_ablation.json`).

Flags and why they exist
------------------------
- `symmetry_mode` : which label-symmetry break (or none). Cheap
  breaks reduce the N! redundant search tree; chained cardinality
  inequalities empirically hurt at small N.
- `ramsey_prune`  : skip (α, d) boxes proved infeasible by the
  Ramsey degree bounds in `utils/ramsey.degree_bounds`. Zero SAT
  cost; every skipped box is a solver call saved.
- `scan_from_ramsey_floor` : begin the d-loop at the Ramsey-derived
  d_min rather than 1. Avoids cheap-to-state but expensive-to-prove
  INFEASIBLE verdicts on trivially-too-small d.

Two run modes, chosen by kwargs:
  - both `alpha` and `d_max` set  → one SAT solve on that box.
  - either missing                → scan the missing dimension(s),
                                    return one graph per α (the one
                                    at the smallest feasible d_max).
"""

import json
import math
import os
import sys
from itertools import combinations

import networkx as nx
import numpy as np
from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.ramsey import degree_bounds as _ramsey_degree_bounds

from .base import Search


_CIRCULANT_CATALOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "graphs", "circulant.json",
)


def _load_circulant_by_n() -> dict[int, "nx.Graph"]:
    """Cache: n → circulant graph from graphs/circulant.json.

    Used only when `circulant_hints=True`. Imports the decoder lazily so
    the import graph of `sat_exact.py` doesn't grow for callers who
    never enable hints.
    """
    try:
        from graph_db.encoding import sparse6_to_nx
    except ImportError:
        return {}
    if not os.path.exists(_CIRCULANT_CATALOG_PATH):
        return {}
    out: dict[int, nx.Graph] = {}
    with open(_CIRCULANT_CATALOG_PATH) as f:
        data = json.load(f)
    for rec in data:
        G = sparse6_to_nx(rec["sparse6"])
        out[G.number_of_nodes()] = G
    return out


_CIRCULANT_BY_N: dict[int, "nx.Graph"] | None = None


def _circulant_for(n: int) -> "nx.Graph | None":
    global _CIRCULANT_BY_N
    if _CIRCULANT_BY_N is None:
        _CIRCULANT_BY_N = _load_circulant_by_n()
    return _CIRCULANT_BY_N.get(n)


_STATUS_NAME = {
    cp_model.OPTIMAL:       "FEASIBLE",
    cp_model.FEASIBLE:      "FEASIBLE",
    cp_model.INFEASIBLE:    "INFEASIBLE",
    cp_model.UNKNOWN:       "TIMEOUT",
    cp_model.MODEL_INVALID: "INVALID",
}

# Supported symmetry-breaking modes.
_SYMMETRY_MODES = ("none", "anchor", "chain", "edge_lex")


class SATExact(Search):
    """
    CP-SAT certified K4-free graph search.

    Base model (always on)
    ----------------------
    Variables : x_{i,j} for every i < j; one bool per potential edge.
    Clauses   :
      * K4-free      — C(n,4) 6-literal disjunctions.
      * Max degree   — Σ incident ≤ d_max per vertex.
      * Independence — C(n, α+1) disjunctions: every (α+1)-subset
                       contains ≥ 1 edge.

    Optional accelerators
    ---------------------
    symmetry_mode : "none" | "anchor" | "chain" | "edge_lex"
        "none"     : no symmetry breaking.
        "anchor"   : deg(0) ≥ deg(v) for every v > 0. One anchor —
                     cheap, breaks most labelling symmetry.
        "chain"    : deg(0) ≥ deg(1) ≥ … ≥ deg(n-1). Stronger but
                     pays for n-1 cardinality inequalities; not always
                     a win at small N.
        "edge_lex" : x[0,1] ≥ x[0,2] ≥ … ≥ x[0,n-1]. Lexicographic
                     order on vertex 0's adjacency row. Pure bool
                     comparisons, no cardinality aux vars.
    ramsey_prune  : bool. Skip (α, d) boxes already infeasible by
                    Ramsey bounds. Default True.
    scan_from_ramsey_floor : bool. In scan mode, start d at the
                             Ramsey-derived d_min. Default True.
    circulant_hints : bool. Pass the matching circulant from
                      `graphs/circulant.json` as a CP-SAT hint.
                      Relabelled cyclically so row-0 is lex-largest,
                      which is the best chance the hint survives the
                      edge_lex break. Default False.
    parallel_alpha : bool. Dispatch each α-track (fixed α, scan over
                     d) to its own worker process. Only intended for
                     a big server — each track keeps its own CP-SAT
                     model, so memory scales with (# α) × model size.
                     Default False.
    parallel_alpha_tracks : int. Number of parallel worker processes
                            when `parallel_alpha=True`. `0` uses one
                            track per α value.
    branch_on_v0 : bool. Add a decision strategy that branches on the
                   vertex-0 row first (CHOOSE_FIRST, SELECT_MAX_VALUE).
                   Complements edge_lex, which already pins that row's
                   ordering. Default False.
    c_log_prune   : bool. Skip any (α, d) box whose target c-bound
                    α·d/(n·ln d) is already ≥ the current best c_log.
                    On the Pareto frontier the smallest-feasible-d
                    witness has α(G)=α and d_max(G)=d, so its actual
                    c_log equals that bound — boxes with bound ≥ c*
                    cannot improve the result. Eliminates the stubborn
                    INFEASIBLE-proof boxes at the feasibility boundary
                    entirely. Default True.
    seed_from_catalog : bool. Seed c* from the best circulant for this
                    n in graphs/circulant.json before the scan starts.
                    Pure win: the stored graph is K4-verified, its
                    c_log is achievable, and every box with worse
                    c-bound prunes without a solver call. Default True.
    seed_from_circulant_search : bool. If the catalog has no entry for
                    this n, enumerate K4-free circulants live via
                    search.CirculantSearch and seed c* from the best.
                    For n ≤ 40 this is seconds at worst (≤ 2^(n/2)
                    subsets filtered by a bitmask K4 check). Default
                    True — it is the only way to keep the scan fast
                    on n values the committed catalog does not cover.

    Run-mode kwargs
    ---------------
    alpha     : int | None   — hard; α(G) ≤ alpha. If None, scanned.
    d_max     : int | None   — hard; d_max(G) ≤ d_max. If None, scanned.
    timeout_s : float        — per SAT solve, default 300.
    workers   : int          — CP-SAT num_search_workers, default 8.
    """

    name = "sat_exact"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        alpha: int | None = None,
        d_max: int | None = None,
        timeout_s: float = 300.0,
        workers: int = 8,
        symmetry_mode: str = "edge_lex",
        ramsey_prune: bool = True,
        scan_from_ramsey_floor: bool = True,
        circulant_hints: bool = False,
        parallel_alpha: bool = False,
        parallel_alpha_tracks: int = 0,
        branch_on_v0: bool = False,
        c_log_prune: bool = True,
        seed_from_catalog: bool = True,
        seed_from_circulant_search: bool = True,
        hard_box_params: bool = False,
        solver_log: bool = False,
        random_seed: int | None = None,
        **kwargs,
    ):
        if symmetry_mode not in _SYMMETRY_MODES:
            raise ValueError(
                f"symmetry_mode={symmetry_mode!r} not in {_SYMMETRY_MODES}"
            )
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            alpha=alpha,
            d_max=d_max,
            timeout_s=timeout_s,
            workers=workers,
            symmetry_mode=symmetry_mode,
            ramsey_prune=ramsey_prune,
            scan_from_ramsey_floor=scan_from_ramsey_floor,
            circulant_hints=circulant_hints,
            parallel_alpha=parallel_alpha,
            parallel_alpha_tracks=parallel_alpha_tracks,
            branch_on_v0=branch_on_v0,
            c_log_prune=c_log_prune,
            seed_from_catalog=seed_from_catalog,
            seed_from_circulant_search=seed_from_circulant_search,
            hard_box_params=hard_box_params,
            solver_log=solver_log,
            random_seed=random_seed,
            **kwargs,
        )

    # ── Ramsey helpers ───────────────────────────────────────────────────────

    def _ramsey_bounds(self, alpha_cap: int) -> tuple[int, int]:
        """Return (d_min, d_max) from Ramsey theory. -1 means unknown."""
        return _ramsey_degree_bounds(self.n, alpha_cap)

    def _ramsey_infeasible(self, alpha_cap: int, d_cap: int) -> bool:
        """True iff the (α, d_cap) box is INFEASIBLE by Ramsey alone."""
        if not self.ramsey_prune:
            return False
        d_min, d_hi = self._ramsey_bounds(alpha_cap)
        # If both bounds known and d_min > d_hi, (n, α) is empty regardless.
        if d_min >= 0 and d_hi >= 0 and d_min > d_hi:
            return True
        # If d_cap can't even reach d_min, the box is empty.
        if d_min >= 0 and d_cap < d_min:
            return True
        return False

    # ── c_log-bound pruning ──────────────────────────────────────────────────

    def _c_bound(self, alpha_cap: int, d_cap: int) -> float:
        """Pareto-tight c_log of any witness for box (α, d). When the
        scan finds (α, d) as the smallest feasible d for α, the witness
        has α(G)=α and d_max(G)=d exactly — so its c_log equals this
        bound. Boxes with _c_bound ≥ c* cannot improve the result."""
        if d_cap <= 1:
            return float("inf")
        return alpha_cap * d_cap / (self.n * math.log(d_cap))

    def _c_min_possible(self, alpha_cap: int) -> float:
        """Lowest c-bound reachable for this α subject to d ≥ Ramsey floor.
        c_bound(α, d) = α·d/(n·ln d) has a minimum over integers at d=3
        (3/ln 3 < 2/ln 2 and ↑ after 3), so below d=3 the minimum is
        α·3/(n·ln 3); at or above d=3 it is α·d_lo/(n·ln d_lo)."""
        d_lo = max(self._d_lo(alpha_cap), 2)
        if d_lo <= 3:
            return self._c_bound(alpha_cap, 3)
        return self._c_bound(alpha_cap, d_lo)

    def _seed_c_star(self) -> tuple[float, "nx.Graph | None"]:
        """Seed (c*, witness) from the best circulant for this n. Tries
        the committed catalog first (O(1) JSON read); if no catalog entry
        exists, falls back to a live CirculantSearch (O(2^(n/2)) bitmask
        checks). Returns (+inf, None) if every source fails.

        The witness is returned so the caller can emit it directly as a
        result — this avoids a redundant SAT re-solve of a box whose
        answer we already hold (and which, empirically, CP-SAT can
        still take minutes to reproduce at n ≥ 19 boundary)."""
        try:
            from utils.graph_props import alpha_exact_nx, c_log_value, is_k4_free_nx
        except ImportError:
            return float("inf"), None

        best = float("inf")
        best_G: "nx.Graph | None" = None

        if self.seed_from_catalog:
            G = _circulant_for(self.n)
            if G is not None and is_k4_free_nx(G):
                degs = dict(G.degree())
                d_actual = max(degs.values()) if degs else 0
                a_actual, _ = alpha_exact_nx(G)
                c = c_log_value(a_actual, self.n, d_actual)
                if c is not None and c < best:
                    best = c
                    best_G = G

        if best == float("inf") and self.seed_from_circulant_search:
            try:
                from search.circulant import CirculantSearch
            except ImportError:
                return best, best_G
            try:
                live = CirculantSearch(
                    n=self.n, top_k=1, verbosity=0,
                ).run()
            except Exception:
                return best, best_G
            if live and live[0].c_log is not None and live[0].c_log < best:
                best = live[0].c_log
                best_G = live[0].G
        return best, best_G

    # ── model ────────────────────────────────────────────────────────────────

    def _build_model(self, alpha_cap: int, d_cap: int):
        n = self.n
        model = cp_model.CpModel()

        x: dict[tuple[int, int], cp_model.IntVar] = {}
        for i in range(n):
            for j in range(i + 1, n):
                x[(i, j)] = model.new_bool_var(f"x_{i}_{j}")

        # K4-free: every 4-set is missing at least one edge. Encoded as
        # a pure 6-literal clause over negated edges (at least one of the
        # six edges is absent). This avoids the linear-cardinality
        # reformulation path CP-SAT would otherwise take for `sum ≤ 5`
        # — unit propagation fires the moment 5 of 6 are fixed to 1.
        for a, b, c, d in combinations(range(n), 4):
            model.add_bool_or([
                x[(a, b)].negated(), x[(a, c)].negated(), x[(a, d)].negated(),
                x[(b, c)].negated(), x[(b, d)].negated(), x[(c, d)].negated(),
            ])

        # Per-vertex degree expression, reused for max-degree and
        # symmetry constraints below.
        def deg_expr(v):
            return sum(
                x[(min(v, u), max(v, u))] for u in range(n) if u != v
            )

        # Max degree.
        for v in range(n):
            model.add(deg_expr(v) <= d_cap)

        # Optional Ramsey-derived lower bound on degree (tightens the
        # model; safe whenever ramsey_prune is enabled).
        if self.ramsey_prune:
            d_min, _ = self._ramsey_bounds(alpha_cap)
            if d_min and d_min > 0:
                for v in range(n):
                    model.add(deg_expr(v) >= d_min)

        # Independence: every (α+1)-subset contains at least one edge.
        # Encoded as a pure disjunction (same reasoning as K4 clauses).
        k = alpha_cap + 1
        if k <= n:
            for subset in combinations(range(n), k):
                edges = [x[(i, j)] for i, j in combinations(subset, 2)]
                model.add_bool_or(edges)


        # Symmetry breaking.
        if self.symmetry_mode == "chain":
            # deg(0) ≥ deg(1) ≥ … ≥ deg(n-1)
            for i in range(n - 1):
                model.add(deg_expr(i) >= deg_expr(i + 1))
        elif self.symmetry_mode == "anchor":
            # deg(0) is (at least tied for) max-degree. Cheaper than
            # the chain: fewer cardinality inequalities, same total
            # anchor effect on the vertex labelled 0.
            for v in range(1, n):
                model.add(deg_expr(0) >= deg_expr(v))
        elif self.symmetry_mode == "edge_lex":
            # Lex-leader symmetry break on column pairs (j, j+1), with
            # one linear inequality per pair. Exponential weights make
            # the sum behave numerically like a lex comparison: the
            # highest-weighted (top) row dominates, and only when it
            # ties does the next row matter. Correct and single-linear.
            #     8·x[0,j] + 4·x[1,j] + 2·x[2,j] + x[3,j]
            #   ≥ 8·x[0,j+1] + 4·x[1,j+1] + 2·x[2,j+1] + x[3,j+1]
            # Row-k is included only when k < j (swap σ=(j,j+1) only
            # touches row-k at columns j, j+1 when k < j). A prefix-
            # sum (equal-weighted) form would over-constrain when row
            # 0 wins but later rows go in the opposite direction.
            k_max = 3  # break rows 0..3
            for j in range(1, n - 1):
                k_end = min(k_max, j - 1)
                lhs = sum(
                    (1 << (k_end - i)) * x[(i, j)] for i in range(k_end + 1)
                )
                rhs = sum(
                    (1 << (k_end - i)) * x[(i, j + 1)]
                    for i in range(k_end + 1)
                )
                model.add(lhs >= rhs)

        # Optional: warm-start hint from the circulant catalog. The
        # catalog holds one hand-picked circulant per n; when its
        # structural (α, d) fits inside the current box we pass it as
        # a CP-SAT hint. Only applied if the hint's labelling happens
        # to satisfy the active symmetry break — otherwise CP-SAT
        # would ignore it anyway. The labelling check below is a
        # cheap feasibility probe for the row-0 edge_lex order.
        if self.circulant_hints:
            self._maybe_hint_circulant(model, x, alpha_cap, d_cap)

        # Optional: tell CP-SAT to branch on vertex 0's row first, trying
        # edge=1 before edge=0. Row 0 is already pinned by edge_lex to be
        # non-increasing, so branching here lets the symmetry constraints
        # and K4 clauses fire at the top of the search tree. Only one
        # worker in the portfolio uses FIXED_SEARCH, so the rest stay
        # free to explore other strategies.
        if self.branch_on_v0:
            row0_vars = [x[(0, j)] for j in range(1, n)]
            model.add_decision_strategy(
                row0_vars,
                cp_model.CHOOSE_FIRST,
                cp_model.SELECT_MAX_VALUE,
            )

        return model, x

    def _maybe_hint_circulant(self, model, x, alpha_cap, d_cap):
        n = self.n
        G = _circulant_for(n)
        if G is None:
            return
        degs = dict(G.degree())
        d_actual = max(degs.values()) if degs else 0
        if d_actual > d_cap:
            return
        # Independence check is expensive; skip and trust the feasibility
        # probe below. If the hint violates independence, CP-SAT drops it.

        # Pick a cyclic relabelling that puts a highest-degree vertex at
        # 0 and sorts its row in non-increasing order (row-0 edge_lex).
        # For a regular circulant every vertex is equivalent; rotations
        # produce the same adjacency structure up to relabel.
        adj = nx.to_numpy_array(G, nodelist=range(n), dtype=int)
        # Try each cyclic rotation and keep the one whose row 0 is
        # lexicographically largest — that's the one most likely to
        # satisfy the edge_lex constraint.
        best_perm = None
        best_row = None
        for shift in range(n):
            perm = [(i + shift) % n for i in range(n)]
            row0 = tuple(adj[perm[0], perm[j]] for j in range(1, n))
            if best_row is None or row0 > best_row:
                best_row = row0
                best_perm = perm
        if best_perm is None:
            return
        for i in range(n):
            for j in range(i + 1, n):
                val = int(adj[best_perm[i], best_perm[j]])
                model.add_hint(x[(i, j)], val)

    def _solve(self, alpha_cap: int, d_cap: int):
        model, x = self._build_model(alpha_cap, d_cap)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = float(self.timeout_s)
        solver.parameters.num_search_workers = int(self.workers)
        if self.hard_box_params:
            # Stubborn INFEASIBLE proofs at the Pareto boundary benefit from
            # max presolve effort: higher linearization so the LP relaxation
            # sees more cuts; stronger probing; max symmetry inference on
            # top of our manual edge_lex break. These are per-box cost at
            # model-build time only; they shouldn't slow easy boxes if the
            # flag is left off.
            solver.parameters.linearization_level = 2
            solver.parameters.cp_model_probing_level = 3
            solver.parameters.symmetry_level = 4
            solver.parameters.cp_model_presolve = True
        if self.solver_log:
            solver.parameters.log_search_progress = True
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
            return status_name, G, solver.wall_time
        return status_name, None, solver.wall_time

    # ── run entry ────────────────────────────────────────────────────────────

    def _run(self) -> list[nx.Graph]:
        if self.alpha is not None and self.d_max is not None:
            return self._single_box(self.alpha, self.d_max)
        return self._scan()

    def _single_box(self, alpha_cap: int, d_cap: int) -> list[nx.Graph]:
        if self._ramsey_infeasible(alpha_cap, d_cap):
            self._log(
                "attempt", level=0,
                alpha=alpha_cap, d_max=d_cap,
                status="INFEASIBLE_RAMSEY", solve_s=0.0,
            )
            return []
        status, G, wt = self._solve(alpha_cap, d_cap)
        self._log(
            "attempt", level=0,
            alpha=alpha_cap, d_max=d_cap, status=status, solve_s=round(wt, 3),
        )
        if G is None:
            return []
        self._stamp(G)
        G.graph["metadata"] = {
            "alpha_target":  alpha_cap,
            "d_max_target":  d_cap,
            "status":        status,
            "solve_s":       round(wt, 3),
        }
        return [G]

    def _d_lo(self, alpha_cap: int) -> int:
        if self.scan_from_ramsey_floor and self.ramsey_prune:
            d_min, _ = self._ramsey_bounds(alpha_cap)
            if d_min and d_min > 0:
                return d_min
        return 1

    def _scan_one_alpha(self, a: int, c_star: float = float("inf")) -> list[nx.Graph]:
        """Scan d for a single α. Used directly in sequential mode and
        via worker processes in parallel-α mode. Any box whose c-bound
        α·d/(n·ln d) already matches or exceeds c_star is skipped — the
        Pareto-tight witness from that box cannot improve c*."""
        n = self.n
        if self.d_max is not None:
            d_range = [self.d_max]
        else:
            d_range = range(self._d_lo(a), n)
        out: list[nx.Graph] = []
        for d in d_range:
            if self._ramsey_infeasible(a, d):
                self._log(
                    "attempt", level=1,
                    alpha=a, d_max=d,
                    status="INFEASIBLE_RAMSEY", solve_s=0.0,
                )
                continue
            if self.c_log_prune and self.d_max is None:
                c_bound = self._c_bound(a, d)
                # Non-strict: c_bound == c_star cannot improve (Pareto
                # witness's c_log would equal c_star, not beat it). If
                # we came in without a seed graph we would still need
                # to solve one tie box so the output is non-empty, but
                # _scan seeds the output with the catalog witness first,
                # so ties are truly dominated and safe to prune.
                if c_bound >= c_star - 1e-9:
                    self._log(
                        "attempt", level=1,
                        alpha=a, d_max=d,
                        status="SKIP_C_BOUND", solve_s=0.0,
                        c_bound=round(c_bound, 4),
                        c_star=round(c_star, 4),
                    )
                    # c_bound is monotone ↑ in d for d ≥ 3, so once it
                    # crosses c_star the rest of the α-track is dead.
                    # Below d=3 (rare; only d=2 is eligible) a later d
                    # may still have c_bound < c_star — keep scanning.
                    if d >= 3:
                        break
                    continue
            status, G, wt = self._solve(a, d)
            self._log(
                "attempt", level=0,
                alpha=a, d_max=d, status=status, solve_s=round(wt, 3),
            )
            if G is None:
                continue
            self._stamp(G)
            G.graph["metadata"] = {
                "alpha_target":  a,
                "d_max_target":  d,
                "status":        status,
                "solve_s":       round(wt, 3),
            }
            out.append(G)
            # Smallest feasible d minimizes c_log for this α
            # (c_log is increasing in d for d ≥ e).
            break
        return out

    def _scan(self) -> list[nx.Graph]:
        n = self.n
        alpha_range = (
            [self.alpha] if self.alpha is not None else list(range(1, n))
        )
        if self.parallel_alpha and len(alpha_range) > 1:
            return self._scan_parallel(alpha_range)
        # Seed c* from the circulant catalog (if any) so the first α
        # track can already prune boundary boxes whose target c-bound
        # exceeds what a known K4-free graph achieves. The seed witness
        # is emitted as a result as well — it is a valid K4-free graph
        # and saves a redundant SAT re-solve for the box it already
        # answers (which at the n≥19 feasibility boundary is often the
        # single slowest box in the scan).
        out: list[nx.Graph] = []
        if self.c_log_prune and self.alpha is None:
            c_star, seed_G = self._seed_c_star()
        else:
            c_star, seed_G = float("inf"), None
        if seed_G is not None:
            self._stamp(seed_G)
            seed_G.graph["metadata"] = {
                "source": "circulant_seed",
                "status": "FEASIBLE",
                "solve_s": 0.0,
            }
            out.append(seed_G)
            self._log(
                "seed_c_star", level=0,
                c_star=round(c_star, 4), source="circulant_catalog",
            )
            # Emit a synthetic ATTEMPT entry for the seed's exact (α, d)
            # box so optimality verifiers parsing the scan log see the
            # box as covered. Without this, a seed-only box would look
            # OPEN despite being backed by a certified K4-free witness.
            from utils.graph_props import alpha_exact_nx
            a_seed, _ = alpha_exact_nx(seed_G)
            d_seed = max(dict(seed_G.degree()).values())
            self._log(
                "attempt", level=0,
                alpha=a_seed, d_max=d_seed,
                status="FEASIBLE_SEED", solve_s=0.0,
            )
        for a in alpha_range:
            if (
                self.c_log_prune and self.alpha is None
                and self._c_min_possible(a) >= c_star - 1e-9
            ):
                self._log(
                    "skip_alpha", level=1,
                    alpha=a,
                    c_min=round(self._c_min_possible(a), 4),
                    c_star=round(c_star, 4),
                )
                continue
            graphs = self._scan_one_alpha(a, c_star=c_star)
            for G in graphs:
                c_actual = self._graph_c_log(G)
                if c_actual is not None and c_actual < c_star:
                    c_star = c_actual
            out.extend(graphs)
        return out

    def _graph_c_log(self, G: nx.Graph) -> float | None:
        """Actual c_log of witness G, computed once to tighten c* during
        the scan. Uses utils.graph_props so the value matches what the
        base class will ultimately report."""
        from utils.graph_props import alpha_exact_nx, c_log_value
        degs = dict(G.degree())
        d_actual = max(degs.values()) if degs else 0
        a_actual, _ = alpha_exact_nx(G)
        return c_log_value(a_actual, self.n, d_actual)

    def _scan_parallel(self, alpha_range: list[int]) -> list[nx.Graph]:
        """Dispatch each α to its own worker process. Server-only —
        each worker holds its own model, so memory footprint scales
        linearly in the number of tracks.
        """
        from concurrent.futures import ProcessPoolExecutor, as_completed

        cfg = {
            "top_k":                  self.top_k,
            "verbosity":              self.verbosity,
            "timeout_s":              self.timeout_s,
            "workers":                self.workers,
            "symmetry_mode":          self.symmetry_mode,
            "ramsey_prune":           self.ramsey_prune,
            "scan_from_ramsey_floor": self.scan_from_ramsey_floor,
            "circulant_hints":        self.circulant_hints,
            "c_log_prune":               self.c_log_prune,
            "seed_from_catalog":         self.seed_from_catalog,
            "seed_from_circulant_search": self.seed_from_circulant_search,
            # d_max propagates so "fixed d, scan α" stays available.
            "d_max":                     self.d_max,
        }
        max_workers = (
            self.parallel_alpha_tracks
            if self.parallel_alpha_tracks and self.parallel_alpha_tracks > 0
            else len(alpha_range)
        )
        results: list[nx.Graph] = []
        with ProcessPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(_scan_one_alpha_worker, self.n, a, cfg): a
                for a in alpha_range
            }
            for fut in as_completed(futures):
                a = futures[fut]
                try:
                    graphs = fut.result()
                except Exception as exc:  # noqa: BLE001
                    self._log(
                        "attempt", level=0,
                        alpha=a, d_max=-1,
                        status=f"WORKER_ERROR: {exc}", solve_s=0.0,
                    )
                    continue
                results.extend(graphs)
        return results


def _scan_one_alpha_worker(n: int, a: int, cfg: dict) -> list[nx.Graph]:
    """Top-level so it survives pickling for ProcessPoolExecutor."""
    s = SATExact(n=n, alpha=a, **cfg)
    return s._scan_one_alpha(a)
