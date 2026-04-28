"""
search/sat_circulant_exact.py
=============================
Provably-optimal K4-free circulant search via explicit MIS encoding.

For a given (N, d, α_target) box we build a CP-SAT model that enforces
α(G(S)) ≤ α_target by adding one clause per (α_target+1)-vertex subset
V ⊂ [N] containing vertex 0: "at least one pairwise gap of V is in S",
i.e. OR_{k ∈ D(V)} g_k. This makes V non-independent in G(S).

Sweeping (d, α_target) in c_log-ascending order and stopping at the first
SAT yields the circulant with **proven** minimum c_log (assuming no
timeouts — proven=False is set if any box returns UNKNOWN).

Differences from `SATCirculant` (CEGAR):
- Explicit all-subsets encoding: α ≤ α_target is enforced structurally,
  no iterative refinement needed. One SAT call per box.
- SAT / INFEASIBLE / UNKNOWN are all distinguishable; UNKNOWN flags
  `proven=False` on the returned graph's metadata.
- Clause count blows up as C(N-1, α_target) — tractable for small
  α_target relative to N. Expect scalability only to N ≲ 40 without
  further clause-reduction tricks (gap-set dedup is already on).

Attached metadata per returned graph:
- `connection_set`      list[int]
- `degree`              int
- `alpha`               int (actual α of found G)
- `proven`              bool (True iff every box resolved SAT/INFEASIBLE)
- `n_boxes_tried`       int
- `status_counts`       dict {INFEASIBLE, OPTIMAL, FEASIBLE, UNKNOWN, …}
- `method`              "exact_mis_clauses"
"""

import os
import sys
import time
from itertools import combinations
from math import ceil, log

import numpy as np
import networkx as nx
from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import alpha_cpsat, c_log_value
from utils.ramsey import R4_UB

from .base import Search
from .sat_circulant import _k4_gap_clauses, _circulant_graph, _fold


# ── helpers ──────────────────────────────────────────────────────────────────


# Best-known upper bounds on R(4, k). For K4-free graphs on N vertices,
# n ≥ R(4, k) implies α(G) ≥ k, so a proven *upper* bound on R(4, k)
# yields a sound α-lower-bound prune. Values for k ≤ 10 come from the
# canonical R4_UB in utils.ramsey; this dict extends to k ≤ 20 via
# Radziszowski's "Small Ramsey Numbers" survey upper bounds.
_RAMSEY_4K_UPPER: dict[int, int] = {
    **R4_UB,
    11: 191,
    12: 238,
    13: 291,
    14: 349,
    15: 417,
    16: 491,
    17: 577,
    18: 668,
    19: 762,
    20: 868,
}


def ramsey_alpha_lb(n: int) -> int:
    """Largest k such that the proven upper bound on R(4, k) is ≤ n —
    equivalently the largest k for which every K4-free graph on n vertices
    provably has α ≥ k. Returns 0 for n < 4."""
    best = 0
    for k, r_ub in _RAMSEY_4K_UPPER.items():
        if r_ub <= n and k > best:
            best = k
    return best


def _alpha_lower_bound(n: int, d: int) -> int:
    """Combined α lower bound: max(Caro-Wei, Ramsey-upper-R(4,k))."""
    cw = ceil(n / (d + 1))
    rm = ramsey_alpha_lb(n)
    return max(cw, rm)


def _enumerate_boxes(n: int, d_min: int, d_max: int | None) -> list[tuple[float, int, int]]:
    """Return (c_log, d, α_target) triples sorted by c_log ascending. Skips
    boxes failing α_target < max(Caro-Wei, Ramsey R(4,·)-inverse)."""
    d_hi = d_max if d_max is not None else min(n - 2, max(6, int(2 * n ** 0.5)))
    boxes: list[tuple[float, int, int]] = []
    for d in range(d_min, d_hi + 1):
        if log(d) <= 0:
            continue
        alpha_lb = _alpha_lower_bound(n, d)
        alpha_hi = min(n - 1, int(n * 0.7))
        for a in range(alpha_lb, alpha_hi + 1):
            c = a * d / (n * log(d))
            boxes.append((c, d, a))
    boxes.sort()
    return boxes


def _subset_clauses(n: int, alpha_target: int):
    """Yield deduplicated gap-sets (as frozenset[int]) for every size-(α_target+1)
    vertex subset of [N] containing 0. Each gap-set corresponds to one clause
    `OR_{k ∈ gaps} g_k` in the SAT model (the subset is non-independent iff
    at least one gap is in S)."""
    seen: set[frozenset] = set()
    for tail in combinations(range(1, n), alpha_target):
        V = (0,) + tail
        gaps: set[int] = set()
        for i in range(len(V)):
            for j in range(i + 1, len(V)):
                k = _fold(V[j] - V[i], n)
                if k > 0:
                    gaps.add(k)
        if not gaps:
            continue
        key = frozenset(gaps)
        if key in seen:
            continue
        seen.add(key)
        yield key


def _solve_box(
    n: int,
    d: int,
    alpha_target: int,
    k4_clauses,
    time_limit: float,
    workers: int,
) -> tuple[str, list[int] | None, int, float]:
    """Solve one (N, d, α_target) box. Returns (status_name, S_or_None,
    n_indep_clauses, wallclock_s)."""
    half = n // 2
    t_build = time.monotonic()
    model = cp_model.CpModel()
    g = [None] + [model.NewBoolVar(f"g_{k}") for k in range(1, half + 1)]

    for gaps in k4_clauses:
        model.AddBoolOr([g[k].Not() for k in gaps])

    if n % 2 == 0:
        model.Add(2 * sum(g[k] for k in range(1, half)) + g[half] == d)
    else:
        model.Add(2 * sum(g[k] for k in range(1, half + 1)) == d)

    n_indep = 0
    for gaps in _subset_clauses(n, alpha_target):
        model.AddBoolOr([g[k] for k in gaps])
        n_indep += 1

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = workers

    t0 = time.monotonic()
    status = solver.Solve(model)
    t_solve = time.monotonic() - t0
    name = solver.StatusName(status)

    S: list[int] | None = None
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        S = [k for k in range(1, half + 1) if solver.Value(g[k]) == 1]

    return name, S, n_indep, time.monotonic() - t_build


# ── search class ─────────────────────────────────────────────────────────────


class SATCirculantExact(Search):
    """
    Exact-optimal K4-free circulant search via all-subsets MIS encoding.

    Iterates boxes (d, α_target) in c_log-ascending order. Each box is one
    CP-SAT call with explicit α ≤ α_target clauses. First SAT is the
    optimum (proven if no prior UNKNOWN timeouts).

    Constraints / kwargs
    --------------------
    d_min, d_max : int | None
        Soft. Degree scan range. Default d_min=3, d_max=min(N-2, max(6, 2√N)).
    time_limit_per_box : float
        Soft. Wall-clock budget per (d, α_target) SAT call. If a box hits this
        and returns UNKNOWN, `proven=False` on the output graph.
    alpha_time_limit : float
        Soft. Time limit for the post-hoc exact α computation on the
        returned S. Separate from the SAT box limit.
    workers : int
        Soft. CP-SAT `num_search_workers` per box.
    best_c_init : float
        Soft. Upper bound on c_log above which boxes are skipped. Default
        1.0 — tighten for known-good initial c.
    """

    name = "sat_circulant_exact"

    def __init__(
        self,
        n: int,
        *,
        top_k: int = 1,
        verbosity: int = 0,
        parent_logger=None,
        d_min: int = 3,
        d_max: int | None = None,
        time_limit_per_box: float = 60.0,
        alpha_time_limit: float = 60.0,
        workers: int = 4,
        best_c_init: float = 1.0,
        **kwargs,
    ):
        super().__init__(
            n,
            top_k=top_k,
            verbosity=verbosity,
            parent_logger=parent_logger,
            d_min=d_min,
            d_max=d_max,
            time_limit_per_box=time_limit_per_box,
            alpha_time_limit=alpha_time_limit,
            workers=workers,
            best_c_init=best_c_init,
            **kwargs,
        )

    # Circulants are vertex-transitive → pin x[0]=1.
    def _alpha_of(self, G: nx.Graph) -> tuple[int, list[int]]:
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_cpsat(adj, vertex_transitive=True)

    def _run(self) -> list[nx.Graph]:
        n = self.n
        if n < 4:
            return []

        k4 = _k4_gap_clauses(n)
        boxes = _enumerate_boxes(n, self.d_min, self.d_max)
        self._log(
            "boxes_enumerated",
            level=1,
            n_boxes=len(boxes),
            n_k4_clauses=len(k4),
        )

        best_c = float(self.best_c_init)
        best_S: list[int] | None = None
        best_d = 0
        best_alpha = 0
        proven = True
        n_tried = 0
        status_counts: dict[str, int] = {}
        box_log: list[dict] = []

        for c_log_box, d, alpha_target in boxes:
            if c_log_box >= best_c - 1e-9:
                # Remaining boxes all have c_log ≥ best_c; done.
                break
            n_tried += 1

            status, S, n_indep, dt = _solve_box(
                n, d, alpha_target, k4,
                time_limit=self.time_limit_per_box,
                workers=self.workers,
            )
            status_counts[status] = status_counts.get(status, 0) + 1
            self._log(
                "box",
                level=1,
                d=d,
                alpha_target=alpha_target,
                c_log_box=round(c_log_box, 6),
                n_indep_clauses=n_indep,
                status=status,
                time_s=round(dt, 2),
            )
            box_log.append({
                "d": d,
                "alpha_target": alpha_target,
                "c_log_box": round(c_log_box, 6),
                "n_indep_clauses": n_indep,
                "status": status,
                "time_s": round(dt, 2),
            })

            if status == "INFEASIBLE":
                continue
            if status in ("OPTIMAL", "FEASIBLE"):
                assert S is not None
                G = _circulant_graph(n, S)
                adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
                actual_alpha, _ = alpha_cpsat(
                    adj,
                    time_limit=self.alpha_time_limit,
                    vertex_transitive=True,
                )
                if actual_alpha <= 0:
                    continue
                c = c_log_value(actual_alpha, n, d)
                if c is None or c >= best_c:
                    continue
                best_c = c
                best_S = S
                best_d = d
                best_alpha = actual_alpha
                # First SAT in c-ascending order is the optimum — done.
                self._log(
                    "new_best",
                    level=0,
                    c_log=round(c, 6),
                    alpha=actual_alpha,
                    d=d,
                    S=S,
                )
                break
            # UNKNOWN / MODEL_INVALID / etc — lose provability, keep trying.
            proven = False

        if best_S is None:
            return []

        G = _circulant_graph(n, best_S)
        self._stamp(G)
        G.graph["metadata"] = {
            "connection_set": list(best_S),
            "degree": int(best_d),
            "alpha": int(best_alpha),
            "proven": bool(proven),
            "n_boxes_tried": int(n_tried),
            "status_counts": dict(status_counts),
            "method": "exact_mis_clauses",
        }
        return [G]
