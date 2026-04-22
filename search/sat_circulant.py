"""
search/sat_circulant.py
=======================
K4-free circulant search via CP-SAT with α-CEGAR.

For each degree d in [d_min, d_max], builds a SAT model with bool gap
indicators g_1..g_{N/2}, adds K4-free clauses over triples, fixes the
degree, and iteratively solves. After each SAT hit we compute exact α
of the candidate circulant; if α exceeds the best-so-far we extract the
witnessing independent set I, add one blocking clause
`OR_{k ∈ D(I)} g_k`, and resolve.

Two properties of the blocking clause we exploit:

1. Circulants are vertex-transitive, so if I is independent then every
   rotation I+t is also independent. D(I) is rotation-invariant, so one
   clause kills the whole rotation orbit.
2. Multiplier action (u · S for u ∈ (Z/NZ)*): we don't canonicalize
   inside the SAT; CP-SAT's symmetry breaking handles most of it and
   the rest is cheap noise.

Differences from CirculantSearchFast:
- No `|S| ≤ max_conn_size` cap (SAT variables are ~N/2 gap bits, not S).
- Uses learned clauses globally, not just branch-local pruning.
- Iterates over explicit (d, α) targets instead of enumerate-and-rank.

Scope
-----
This search targets N in [10, ~300] on this host. Past 300 the K4-clause
count (~C(N/2, 3)) and α-CEGAR iterations both grow; commit to the
cluster run rather than local.
"""

import json
import os
import sys
import time
from math import ceil, log

import numpy as np
import networkx as nx
from ortools.sat.python import cp_model

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.graph_props import alpha_cpsat, c_log_value

from .base import Search


# ── circulant primitives ─────────────────────────────────────────────────────


def _fold(x: int, n: int) -> int:
    x = x % n
    return x if 2 * x <= n else n - x


def _circulant_adj(n: int, S_half: list[int]) -> np.ndarray:
    S_full: set[int] = set()
    for s in S_half:
        S_full.add(s % n)
        S_full.add((n - s) % n)
    S_arr = np.fromiter(S_full, dtype=np.int64, count=len(S_full))
    adj = np.zeros((n, n), dtype=np.uint8)
    for i in range(n):
        adj[i, (i + S_arr) % n] = 1
    return adj


def _circulant_graph(n: int, S_half: list[int]) -> nx.Graph:
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for s in S_half:
            G.add_edge(i, (i + s) % n)
            G.add_edge(i, (i - s) % n)
    return G


def _enum_mis_circulant(
    S_half: list[int],
    n: int,
    alpha: int,
    max_count: int = 5,
) -> list[list[int]]:
    """
    Enumerate up to `max_count` size-α independent sets of C(n, S_half)
    that contain vertex 0. DFS over vertex additions; prune when any
    difference to a chosen vertex falls in S.

    Only enumerates vertex-0-containing sets — sufficient because we
    only need D(I), which is invariant under rotation of I.
    """
    S: set[int] = set()
    for s in S_half:
        S.add(s % n)
        S.add((n - s) % n)

    results: list[list[int]] = []

    def dfs(last: int, chosen: list[int], size_left: int) -> bool:
        if size_left == 0:
            results.append(list(chosen))
            return len(results) >= max_count
        for v in range(last + 1, n):
            if v in S:
                continue
            ok = True
            for c in chosen:
                if (v - c) % n in S:
                    ok = False
                    break
            if ok:
                chosen.append(v)
                if dfs(v, chosen, size_left - 1):
                    return True
                chosen.pop()
        return False

    dfs(0, [0], alpha - 1)
    return results


# ── K4-free clause enumeration ────────────────────────────────────────────────


def _k4_gap_clauses(n: int) -> list[tuple[int, ...]]:
    """
    Return the list of distinct gap-sets (sorted tuple, deduped) that
    witness a K4 in any circulant C(n, S). Each corresponds to a clause
    "at least one of these gaps is NOT in S".

    A K4 on {0, a, a+b, a+b+c} (0 < a, b, c, a+b+c < n) has gaps (folded
    to {1..n/2}): {a, b, c, a+b, b+c, a+b+c}. We dedupe by the
    uint64-packed sorted 6-tuple.
    """
    if n < 4:
        return []
    assert n <= 2048, "pack width assumes gap < 2^11"
    BITS = 11
    MASK = (1 << BITS) - 1

    blocks = []
    for a in range(1, n - 2):
        fa = _fold(a, n)
        for b in range(1, n - a - 1):
            c_max = n - a - b - 1
            if c_max < 1:
                continue
            fb = _fold(b, n)
            fab = _fold(a + b, n)

            cs = np.arange(1, c_max + 1, dtype=np.int64)
            fcs = np.where(2 * cs <= n, cs, n - cs)
            bcs = b + cs
            fbcs = np.where(2 * bcs <= n, bcs, n - bcs)
            abcs = a + b + cs
            fabcs = np.where(2 * abcs <= n, abcs, n - abcs)

            stk = np.stack(
                [
                    np.full_like(cs, fa),
                    np.full_like(cs, fb),
                    fcs,
                    np.full_like(cs, fab),
                    fbcs,
                    fabcs,
                ],
                axis=1,
            )
            stk.sort(axis=1)
            packed = (
                (stk[:, 0].astype(np.uint64) << (BITS * 5))
                | (stk[:, 1].astype(np.uint64) << (BITS * 4))
                | (stk[:, 2].astype(np.uint64) << (BITS * 3))
                | (stk[:, 3].astype(np.uint64) << (BITS * 2))
                | (stk[:, 4].astype(np.uint64) << BITS)
                | stk[:, 5].astype(np.uint64)
            )
            blocks.append(packed)

    if not blocks:
        return []
    flat = np.concatenate(blocks)
    uniq = np.unique(flat)

    out = []
    for key in uniq.tolist():
        k = int(key)
        parts = (
            (k >> (BITS * 5)) & MASK,
            (k >> (BITS * 4)) & MASK,
            (k >> (BITS * 3)) & MASK,
            (k >> (BITS * 2)) & MASK,
            (k >> BITS) & MASK,
            k & MASK,
        )
        out.append(tuple(sorted(set(parts))))
    return out


# ── search class ─────────────────────────────────────────────────────────────


class SATCirculant(Search):
    """
    SAT-based K4-free circulant search. Iterates degrees in [d_min, d_max],
    and per degree runs α-CEGAR to find a minimal-α circulant.

    Constraints / kwargs
    --------------------
    d_min : int
        Hard. Minimum degree scanned. Default 3.
    d_max : int | None
        Hard. Maximum degree scanned. Default ceil(sqrt(N)) · 2
        (generous upper bound for the regime where c_log is interesting).
    time_limit_per_box : float
        Soft. Wall-clock budget per degree box.
    max_cegar_iter : int
        Hard. Cap on CEGAR iterations per degree box.
    num_workers : int
        Soft. CP-SAT `num_search_workers`.
    """

    name = "sat_circulant"

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
        max_cegar_iter: int = 200,
        num_workers: int = 4,
        mis_per_iter: int = 5,
        warm_start: bool = True,
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
            max_cegar_iter=max_cegar_iter,
            num_workers=num_workers,
            mis_per_iter=mis_per_iter,
            warm_start=warm_start,
            **kwargs,
        )

    # Circulants are vertex-transitive → pin x[0]=1 in α solver.
    def _alpha_of(self, G: nx.Graph) -> tuple[int, list[int]]:
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        return alpha_cpsat(adj, vertex_transitive=True)

    def _exact_alpha(self, S_half: list[int]) -> tuple[int, list[int]]:
        adj = _circulant_adj(self.n, S_half)
        return alpha_cpsat(adj, vertex_transitive=True)

    def _warm_start_circulant(self) -> tuple[dict[int, list[int]], float | None]:
        """
        Generate a fast warm-start via CirculantSearchFast (DFS with |S|≤6,
        greedy α). Returns (map from degree -> S_half, best c_log).

        The warm start seeds CP-SAT hints and pre-loads `best_c_so_far`,
        which lets the Caro-Wei early-skip activate sooner for degrees
        that can't beat the DFS baseline. Self-contained — does not read
        from graph_db.
        """
        from .circulant_fast import CirculantSearchFast

        per_d: dict[int, tuple[float, list[int]]] = {}
        overall_best: float | None = None
        try:
            warm = CirculantSearchFast(
                n=self.n,
                top_k=10,
                max_conn_size=6,
                min_conn_size=1,
                verbosity=0,
            )
            results = warm.run()
        except Exception:
            return {}, None

        for r in results:
            md = r.metadata or {}
            conn = md.get("connection_set")
            if not isinstance(conn, list) or not conn:
                continue
            d = int(r.d_max)
            c = float(r.c_log) if r.c_log is not None else float("inf")
            prev = per_d.get(d)
            if prev is None or c < prev[0]:
                per_d[d] = (c, [int(x) for x in conn])
            if overall_best is None or c < overall_best:
                overall_best = c
        return {d: s for d, (_, s) in per_d.items()}, overall_best

    # ── main loop ────────────────────────────────────────────────────────────

    def _run(self) -> list[nx.Graph]:
        n = self.n
        if n < 4:
            return []

        t0 = time.monotonic()
        clauses = _k4_gap_clauses(n)
        t_clauses = time.monotonic() - t0
        self._log("k4_clauses_built", level=1, n_clauses=len(clauses), t_s=round(t_clauses, 3))

        d_lo = self.d_min
        d_hi = self.d_max if self.d_max is not None else min(n - 2, max(6, int(2 * n**0.5)))

        # Warm-start: generate seed circulants via DFS for hinting + early skip.
        per_d_hints: dict[int, list[int]] = {}
        best_c_so_far = float("inf")
        all_candidates: list[tuple[float, int, int, list[int], int]] = []
        if self.warm_start:
            t_w = time.monotonic()
            hints, best_c = self._warm_start_circulant()
            per_d_hints = hints
            if best_c is not None:
                best_c_so_far = best_c
            self._log(
                "warm_start",
                level=1,
                n_hints=len(per_d_hints),
                best_c_so_far=None if best_c is None else round(best_c, 6),
                t_s=round(time.monotonic() - t_w, 3),
            )
            # Seed `all_candidates` with the DFS results so the search returns
            # at minimum what circulant_fast found, even if SAT improves nothing.
            for d, S_half in per_d_hints.items():
                G = _circulant_graph(n, S_half)
                alpha, _ = self._alpha_of(G)
                if alpha > 0:
                    c = c_log_value(alpha, n, d)
                    if c is not None:
                        all_candidates.append((c, d, alpha, S_half, 0))

        for d in range(d_lo, d_hi + 1):
            if d < 2:
                continue
            # Caro-Wei: α ≥ ceil(N/(d+1)) for any d-regular graph.
            alpha_cw = ceil(n / (d + 1))

            # Early-skip d if even at α=alpha_cw we can't beat current best.
            c_lb = alpha_cw * d / (n * log(d)) if log(d) > 0 else float("inf")
            if c_lb >= best_c_so_far:
                self._log(
                    "skip_d",
                    level=2,
                    d=d,
                    reason="caro_wei_lb_not_competitive",
                    c_lb=round(c_lb, 5),
                    best_c=round(best_c_so_far, 5),
                )
                continue

            res = self._solve_degree(d, alpha_cw, clauses, hint=per_d_hints.get(d))
            if res is None:
                continue
            alpha, S_half, iters = res
            c = c_log_value(alpha, n, d)
            if c is None:
                continue
            all_candidates.append((c, d, alpha, S_half, iters))
            if c < best_c_so_far:
                best_c_so_far = c
                self._log(
                    "new_best_d",
                    level=1,
                    d=d,
                    alpha=alpha,
                    c_log=round(c, 6),
                    iters=iters,
                    S=S_half,
                )

        if not all_candidates:
            return []

        all_candidates.sort(key=lambda t: t[0])
        out: list[nx.Graph] = []
        for c, d, alpha, S_half, iters in all_candidates[: self.top_k]:
            G = _circulant_graph(n, S_half)
            self._stamp(G)
            G.graph["metadata"] = {
                "connection_set": S_half,
                "degree": d,
                "alpha": alpha,
                "cegar_iters": iters,
                "method": "sat_cegar",
            }
            out.append(G)
        return out

    # ── per-degree CEGAR ─────────────────────────────────────────────────────

    def _solve_degree(
        self,
        d: int,
        alpha_cw: int,
        clauses: list[tuple[int, ...]],
        hint: list[int] | None = None,
    ) -> tuple[int, list[int], int] | None:
        """
        Find a K4-free circulant with deg=d and smallest α found within
        budget. Returns (alpha, S_half, total_iters) or None on failure.
        """
        n = self.n
        half = n // 2

        model = cp_model.CpModel()
        g = [None] + [model.NewBoolVar(f"g_{k}") for k in range(1, half + 1)]

        for gaps in clauses:
            model.AddBoolOr([g[k].Not() for k in gaps])

        # Degree: sum of 2*g[k] for k=1..half-1, plus 1*g[half] if N even.
        if n % 2 == 0:
            model.Add(2 * sum(g[k] for k in range(1, half)) + g[half] == d)
        else:
            model.Add(2 * sum(g[k] for k in range(1, half + 1)) == d)

        # Warm-start hint: CP-SAT uses these values as an initial branching
        # suggestion. If the hinted S is feasible (K4-free, correct degree),
        # the first solve returns it, which skips exploration of equivalent
        # multiplier-orbit solutions and jumps straight to CEGAR improvement.
        if hint:
            hint_set = set(hint)
            for k in range(1, half + 1):
                model.AddHint(g[k], 1 if k in hint_set else 0)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = max(1.0, self.time_limit_per_box / 10)
        solver.parameters.num_search_workers = self.num_workers

        t_start = time.monotonic()
        total_iters = 0
        best: tuple[int, list[int]] | None = None

        while total_iters < self.max_cegar_iter:
            if time.monotonic() - t_start > self.time_limit_per_box:
                break

            status = solver.Solve(model)
            total_iters += 1

            if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
                # UNSAT (with accumulated blocking clauses) or timeout.
                break

            S_half = [k for k in range(1, half + 1) if solver.Value(g[k]) == 1]
            alpha, I = self._exact_alpha(S_half)

            if alpha <= 0:
                # α solver failure; back out.
                break

            if best is None or alpha < best[0]:
                best = (alpha, S_half)
                self._log(
                    "cegar_improve",
                    level=2,
                    d=d,
                    iter=total_iters,
                    alpha=alpha,
                    S=S_half,
                )
                if alpha <= alpha_cw:
                    # Hit Caro-Wei lower bound; can't improve further.
                    break

            # Block multiple size-α MIS per iter (the exact one from the
            # α solver + up to `mis_per_iter - 1` more via circulant DFS).
            # Each MIS I gives a clause "OR g_k for k in D(I)" — at least
            # one pairwise difference of I must be in S, so I is not
            # independent in the next candidate circulant. This avoids
            # CP-SAT repeatedly returning multiplier-isomorphic S's with
            # the same α.
            mis_list: list[list[int]] = [I]
            if self.mis_per_iter > 1:
                extras = _enum_mis_circulant(
                    S_half, n, alpha, max_count=self.mis_per_iter
                )
                for J in extras:
                    if sorted(J) != sorted(I):
                        mis_list.append(J)
                        if len(mis_list) >= self.mis_per_iter:
                            break

            blocked_any = False
            for J in mis_list:
                D_J: set[int] = set()
                J_sorted = sorted(J)
                for i in range(len(J_sorted)):
                    for j in range(i + 1, len(J_sorted)):
                        D_J.add(_fold(J_sorted[j] - J_sorted[i], n))
                D_J.discard(0)
                if D_J:
                    model.AddBoolOr([g[k] for k in D_J])
                    blocked_any = True
            if not blocked_any:
                break

        if best is None:
            return None
        return (best[0], best[1], total_iters)
