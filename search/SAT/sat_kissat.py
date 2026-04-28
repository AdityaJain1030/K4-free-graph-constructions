"""
search/SAT/sat_kissat.py
=========================
External-solver feasibility search for K4-free graphs via KISSAT
(Armin Biere's CDCL SAT solver, https://github.com/arminbiere/kissat).

Mirrors `search/SAT/sat.py` in semantics — same K4-free + α + degree
encoding, same `ramsey_prune` and `edge_lex` flags — but routes the
formula through DIMACS to the `kissat` binary instead of CP-SAT.

Why bother
----------
KISSAT is a pure CDCL/inprocessing solver and a multi-year SAT
Competition champion. Its conflict-learning machinery is among the
fastest in the world, so it is a credible alternative to CP-SAT
specifically on **UNSAT-heavy** boxes — the boundary boxes where the
c_log frontier sits and CP-SAT gets stuck.

Cost: degree constraints (cardinality at-most-k) have to be expanded
to pure clauses, since DIMACS has no native cardinality. Two
encodings are supported via the `degree_encoding` kwarg:

- `"sinz"` (default): Sinz 2005 sequential-counter encoding. Adds
  O(n·d) aux variables and O(n·d) binary/ternary clauses per vertex.
  Total ~O(n²·d) clauses across all vertices — orders of magnitude
  smaller than pairwise blocking on our typical (n, d) regime.
- `"pairwise"`: pairwise-blocking, one (d+1)-clause per (d+1)-subset
  of potential neighbors. Sound but blows up: at (n=20, d=6) it
  produces ~1 M degree clauses vs ~2 K under sequential-counter.

Required binary
---------------
The `kissat` executable must be on PATH. Build via
`scripts/setup_kissat.sh` — that drops it into the conda env and
wires up the activation hook. See `experiments/SAT/NEXT.md` §P6.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from itertools import combinations

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from search.base import Search


# Best-known upper bounds on R(4, k), k >= 2. Mirror of sat.py table —
# kept local to avoid an import that creates a circular dependency
# during the SATKissat path.
_R4_UB: dict[int, int] = {
    2: 4, 3: 9, 4: 18, 5: 25, 6: 36, 7: 58, 8: 79, 9: 106, 10: 136,
}


def _ramsey_prune(n: int, alpha: int, d_max: int) -> tuple[str, str] | None:
    """Same elementary infeasibility rules as sat.py."""
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
    ub = _R4_UB.get(k)
    if ub is not None and n >= ub:
        return ("ramsey_4_k",
                f"n={n} ≥ R(4,{k}) ≤ {ub} ⇒ K4-free forces α ≥ {k}")
    return None


class SATKissat(Search):
    """
    K4-free feasibility search via the KISSAT SAT solver.

    Required kwargs
    ---------------
    alpha   : int — independence-number upper bound, α(G) ≤ alpha.
    d_max   : int — max-degree upper bound, Δ(G) ≤ d_max.

    Optional kwargs
    ---------------
    time_limit_s : float — wall-clock cap passed to kissat (default 60).
    ramsey_prune : bool  — pre-solve box prune (default True).
    edge_lex     : bool  — row-0 lex symmetry break (default True).
    degree_encoding : "sinz" | "pairwise" — at-most-k cardinality
                           encoding for the degree constraint.
                           Default "sinz" (compact, O(n·d) clauses).
    kissat_path  : str   — explicit path to the kissat binary.
                           Defaults to PATH lookup.
    extra_args   : list[str] — passed verbatim to kissat after the
                           DIMACS file. E.g. ['--sat'] to bias for SAT
                           witnesses, or ['-q'] for quiet output.

    Returns
    -------
    Always [G] (length-1 list). On SAT, G is the witness graph. On
    UNSAT or TIMED_OUT, G is the empty graph on n vertices. Inspect
    G.graph["metadata"]["status"].
    """

    name = "sat_kissat"

    def __init__(
        self,
        n: int,
        *,
        alpha: int,
        d_max: int,
        time_limit_s: float = 60.0,
        ramsey_prune: bool = True,
        edge_lex: bool = True,
        degree_encoding: str = "sinz",
        kissat_path: str | None = None,
        extra_args: list[str] | None = None,
        **kwargs,
    ):
        if degree_encoding not in ("sinz", "pairwise"):
            raise ValueError(
                f"degree_encoding must be 'sinz' or 'pairwise', got {degree_encoding!r}"
            )
        super().__init__(
            n,
            alpha=alpha,
            d_max=d_max,
            time_limit_s=time_limit_s,
            ramsey_prune=ramsey_prune,
            edge_lex=edge_lex,
            degree_encoding=degree_encoding,
            kissat_path=kissat_path,
            extra_args=list(extra_args) if extra_args else [],
            **kwargs,
        )

    # ── DIMACS encoding ──────────────────────────────────────────────────────

    @staticmethod
    def _sinz_at_most_k(
        lits: list[int],
        k: int,
        next_var: int,
        clauses: list[list[int]],
    ) -> int:
        """Sinz 2005 sequential-counter encoding of sum(lits) <= k.

        Introduces auxiliary variables s[i,j] for 1 ≤ i ≤ n, 1 ≤ j ≤ k
        with semantics: s[i,j] true ⇒ at least j of lits[0..i-1] are
        true. Adds O(n*k) binary and ternary clauses; same SAT
        feasibility as the pairwise-blocking expansion but without the
        binomial blow-up.

        Returns the next free DIMACS var index after allocating the
        aux variables.
        """
        n = len(lits)
        if k < 0:
            # Infeasible: sum cannot be < 0. Add a contradiction.
            clauses.append([1])
            clauses.append([-1])
            return next_var
        if k >= n:
            # Trivially satisfied — sum ≤ n always holds.
            return next_var
        if k == 0:
            # All literals must be false.
            for lit in lits:
                clauses.append([-lit])
            return next_var

        # Allocate s[i,j] for i in 1..n, j in 1..k. Use a flat list
        # indexed as s[(i-1)*k + (j-1)].
        s_base = next_var
        next_var += n * k

        def s(i: int, j: int) -> int:
            return s_base + (i - 1) * k + (j - 1)

        # i = 1
        # y_1 -> s[1,1]
        clauses.append([-lits[0], s(1, 1)])

        # i = 2..n
        for i in range(2, n + 1):
            yi = lits[i - 1]
            # y_i -> s[i,1]
            clauses.append([-yi, s(i, 1)])
            # s[i-1,1] -> s[i,1]
            clauses.append([-s(i - 1, 1), s(i, 1)])
            for j in range(2, k + 1):
                # s[i-1,j] -> s[i,j]
                clauses.append([-s(i - 1, j), s(i, j)])
                # y_i ∧ s[i-1,j-1] -> s[i,j]
                clauses.append([-yi, -s(i - 1, j - 1), s(i, j)])
            # Bound: ¬s[i-1,k] ∨ ¬y_i (cannot push count past k).
            clauses.append([-s(i - 1, k), -yi])

        return next_var

    def _build_dimacs(self) -> tuple[str, dict[tuple[int, int], int]]:
        """Build DIMACS CNF for the (n, α, d_max) box plus optional
        edge_lex row-0 break. Returns (cnf_text, var_index)."""
        n = self.n
        alpha = self.alpha
        d_max = self.d_max

        # Variable index: 1-based DIMACS literal per edge (i, j), i<j.
        var_idx: dict[tuple[int, int], int] = {}
        next_var = 1
        for i, j in combinations(range(n), 2):
            var_idx[(i, j)] = next_var
            next_var += 1

        def lit(i: int, j: int, sign: int = 1) -> int:
            v = var_idx[(min(i, j), max(i, j))]
            return sign * v

        clauses: list[list[int]] = []

        # (C1) K4-free: for every 4-subset, at least one of the 6 edges
        # is absent.
        for S in combinations(range(n), 4):
            cl = [lit(a, b, -1) for a, b in combinations(S, 2)]
            clauses.append(cl)

        # (C2) α-bound: every (α+1)-subset contains at least one edge.
        if alpha + 1 <= n:
            for T in combinations(range(n), alpha + 1):
                cl = [lit(a, b, +1) for a, b in combinations(T, 2)]
                clauses.append(cl)

        # (C3) degree ≤ d_max.
        if d_max < n - 1:
            if self.degree_encoding == "pairwise":
                # For each vertex v and each (d_max+1)-subset W of its
                # potential neighbors, at least one edge is absent.
                for v in range(n):
                    neighbors = [u for u in range(n) if u != v]
                    for W in combinations(neighbors, d_max + 1):
                        cl = [lit(v, w, -1) for w in W]
                        clauses.append(cl)
            else:  # "sinz"
                # Sinz sequential counter, one independent counter per
                # vertex v over its (n-1) incident edge variables.
                for v in range(n):
                    incident = [lit(v, u, +1) for u in range(n) if u != v]
                    next_var = self._sinz_at_most_k(
                        incident, d_max, next_var, clauses,
                    )

        # Row-0 lex symmetry break: x[0,j] >= x[0,j+1] is equivalent to
        # the binary clause (x[0,j] ∨ ¬x[0,j+1]).
        if self.edge_lex and n >= 3:
            for j in range(1, n - 1):
                clauses.append([lit(0, j, +1), lit(0, j + 1, -1)])

        n_vars = next_var - 1
        n_clauses = len(clauses)
        lines = [f"p cnf {n_vars} {n_clauses}"]
        for cl in clauses:
            lines.append(" ".join(str(x) for x in cl) + " 0")
        return "\n".join(lines) + "\n", var_idx

    # ── KISSAT invocation + output parsing ────────────────────────────────────

    def _resolve_kissat(self) -> str:
        path = self.kissat_path or shutil.which("kissat")
        if not path:
            raise FileNotFoundError(
                "kissat binary not found on PATH. Build it via "
                "scripts/setup_kissat.sh, or pass kissat_path=<...>."
            )
        return path

    @staticmethod
    def _parse_output(stdout: str) -> tuple[str, set[int]]:
        """Parse kissat's DIMACS-style output. Returns
        (status_token, set_of_true_var_indices)."""
        status = "UNKNOWN"
        true_vars: set[int] = set()
        for line in stdout.splitlines():
            if line.startswith("s "):
                token = line[2:].strip()
                if token == "SATISFIABLE":
                    status = "SAT"
                elif token == "UNSATISFIABLE":
                    status = "UNSAT"
                elif token == "UNKNOWN":
                    status = "UNKNOWN"
            elif line.startswith("v "):
                for tok in line[2:].split():
                    try:
                        v = int(tok)
                    except ValueError:
                        continue
                    if v > 0:
                        true_vars.add(v)
        return status, true_vars

    # ── main entrypoint ──────────────────────────────────────────────────────

    def _empty_graph_with_meta(self, **meta) -> nx.Graph:
        G = nx.Graph()
        G.add_nodes_from(range(self.n))
        self._stamp(G)
        G.graph["metadata"] = meta
        return G

    def _run(self) -> list[nx.Graph]:
        n = self.n
        alpha = self.alpha
        d_max = self.d_max

        if n <= 0:
            return []

        # ---------- pre-solve pruning ----------
        if self.ramsey_prune:
            pruned = _ramsey_prune(n, alpha, d_max)
            if pruned is not None:
                rule, reason = pruned
                self._log("ramsey_pruned", rule=rule, reason=reason)
                return [self._empty_graph_with_meta(
                    status="UNSAT",
                    alpha_bound=alpha,
                    d_max_bound=d_max,
                    pruned_by=rule,
                    pruned_reason=reason,
                    time_limit_s=self.time_limit_s,
                    wall_time_s=0.0,
                )]

        # ---------- build CNF ----------
        cnf_text, var_idx = self._build_dimacs()
        # Reverse map: var index → (i, j)
        edge_of: dict[int, tuple[int, int]] = {v: ij for ij, v in var_idx.items()}
        n_vars = len(var_idx)
        n_clauses = cnf_text.count("\n") - 1  # minus header

        # ---------- run kissat ----------
        kissat = self._resolve_kissat()
        with tempfile.TemporaryDirectory(prefix="kissat_k4_") as tmp:
            cnf_path = os.path.join(tmp, "model.cnf")
            with open(cnf_path, "w") as fh:
                fh.write(cnf_text)

            cmd = [kissat,
                   f"--time={int(max(1, self.time_limit_s))}",
                   *self.extra_args, cnf_path]

            self._log(
                "kissat_invoke",
                kissat=kissat, n_vars=n_vars, n_clauses=n_clauses,
                time_limit_s=self.time_limit_s,
            )
            t0 = time.monotonic()
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=self.time_limit_s + 5.0,
                )
                stdout = proc.stdout
                returncode = proc.returncode
                timed_out = False
            except subprocess.TimeoutExpired as exc:
                stdout = exc.stdout.decode() if exc.stdout else ""
                returncode = -1
                timed_out = True
            wall = round(time.monotonic() - t0, 4)

        # ---------- parse + decode ----------
        status, true_vars = self._parse_output(stdout)
        if timed_out and status == "UNKNOWN":
            status = "TIMED_OUT"

        # Map kissat's internal exit-codes for sanity logging.
        # (10 = SAT, 20 = UNSAT, 0 = unknown / timeout)
        self._log(
            "kissat_done",
            status=status, returncode=returncode, wall_time_s=wall,
        )

        G = nx.Graph()
        G.add_nodes_from(range(n))
        if status == "SAT":
            for v in true_vars:
                ij = edge_of.get(v)
                if ij is not None:
                    G.add_edge(*ij)

        verdict = "SAT" if status == "SAT" else (
            "UNSAT" if status == "UNSAT" else "TIMED_OUT"
        )

        self._stamp(G)
        G.graph["metadata"] = {
            "status":       verdict,
            "alpha_bound":  alpha,
            "d_max_bound":  d_max,
            "time_limit_s": self.time_limit_s,
            "wall_time_s":  wall,
            "n_vars":       n_vars,
            "n_clauses":    n_clauses,
            "kissat_path":  kissat,
            "kissat_rc":    returncode,
        }
        return [G]
