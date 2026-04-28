"""
search/SAT/cube_and_conquer.py
==============================
Minimal cube-and-conquer driver for the K4-free SAT pipeline.

Strategy (intentionally simple — for benchmarking the parallelism
gain, not for matching march_cu's quality):

1. Build the CNF via SATKissat._build_dimacs.
2. Pick `cube_depth` branching variables — the first `cube_depth`
   row-0 edge variables (vertex 0's adjacency to vertices 1..cube_depth).
   Row 0 is the natural place to branch because edge_lex already
   forces it monotone; here we drop the lex constraint and split on
   the actual values.
3. Enumerate the 2^cube_depth cubes (full assignments to the chosen
   vars). Each cube is a small set of unit literals.
4. For each cube: append unit clauses to the formula and dispatch
   kissat in a process pool. Whoever wins (SAT) short-circuits the
   pool; UNSAT cubes are accumulated.
5. Aggregate: any cube SAT ⇒ formula SAT (return that cube's
   witness). All cubes UNSAT ⇒ formula UNSAT.

Failure modes (vs march_cu lookahead):
- We don't measure how much each branch propagates, so cubes can
  imbalance wildly. A few cubes hog all the time; the rest finish
  in milliseconds. Still better than 1-core, just not optimal.
- We branch on row-0 instead of high-impact variables anywhere in
  the formula. Sound but weaker.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from itertools import combinations, product
from typing import Iterable

import networkx as nx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from search.base import Search
from search.SAT.sat_kissat import SATKissat, _ramsey_prune


def _write_cube_cnf(base_cnf: str, cube_lits: tuple[int, ...]) -> str:
    """Append `cube_lits` as unit clauses to a CNF file, returning the
    new file path. Caller is responsible for deletion."""
    with open(base_cnf) as fh:
        body = fh.read()
    header, rest = body.split("\n", 1)
    parts = header.split()
    n_vars = int(parts[2])
    n_clauses = int(parts[3])
    new_header = f"p cnf {n_vars} {n_clauses + len(cube_lits)}"
    extra = "\n".join(f"{lit} 0" for lit in cube_lits) + "\n"
    fd, path = tempfile.mkstemp(suffix=".cnf")
    with os.fdopen(fd, "w") as fh:
        fh.write(new_header + "\n")
        fh.write(rest)
        fh.write(extra)
    return path


def _parse_kissat_stdout(stdout: str) -> tuple[str, set[int]]:
    status = "UNKNOWN"
    true_vars: set[int] = set()
    for line in stdout.splitlines():
        if line.startswith("s "):
            tok = line[2:].strip()
            if tok == "SATISFIABLE": status = "SAT"
            elif tok == "UNSATISFIABLE": status = "UNSAT"
        elif line.startswith("v "):
            for t in line[2:].split():
                try:
                    v = int(t)
                except ValueError:
                    continue
                if v > 0:
                    true_vars.add(v)
    return status, true_vars


class SATCubeAndConquer(Search):
    """
    Cube-and-conquer wrapper around `SATKissat`.

    Required kwargs
    ---------------
    alpha   : int — independence-number upper bound.
    d_max   : int — max-degree upper bound.

    Optional kwargs
    ---------------
    cube_depth     : int — number of variables to branch on (default 4
                          → 16 cubes).
    n_workers      : int — process pool size (default min(cube_count,
                          os.cpu_count())).
    time_limit_s   : float — overall wall-clock budget (default 60).
    cube_time_limit_s : float — per-cube budget (default = time_limit_s).
    edge_lex       : bool — keep row-0 lex break (default True; note:
                          if branching on row 0 vars, the cube already
                          fixes them, so lex is a no-op in those cubes).
    degree_encoding : "sinz" | "pairwise" — same as SATKissat.
    kissat_path    : str — explicit kissat binary path.
    extra_args     : list[str] — passed to each per-cube kissat call.
                          E.g. `['--unsat']` is the right preset for
                          UNSAT-direction cubes.
    """

    name = "sat_cnc"

    def __init__(
        self,
        n: int,
        *,
        alpha: int,
        d_max: int,
        cube_depth: int = 4,
        n_workers: int | None = None,
        time_limit_s: float = 60.0,
        cube_time_limit_s: float | None = None,
        edge_lex: bool = True,
        degree_encoding: str = "sinz",
        kissat_path: str | None = None,
        extra_args: list[str] | None = None,
        ramsey_prune: bool = True,
        **kwargs,
    ):
        super().__init__(
            n,
            alpha=alpha,
            d_max=d_max,
            cube_depth=cube_depth,
            n_workers=n_workers,
            time_limit_s=time_limit_s,
            cube_time_limit_s=cube_time_limit_s or time_limit_s,
            edge_lex=edge_lex,
            degree_encoding=degree_encoding,
            kissat_path=kissat_path,
            extra_args=list(extra_args) if extra_args else [],
            ramsey_prune=ramsey_prune,
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
        d_max = self.d_max

        if n <= 0:
            return []

        if self.ramsey_prune:
            pruned = _ramsey_prune(n, alpha, d_max)
            if pruned is not None:
                rule, reason = pruned
                self._log("ramsey_pruned", rule=rule, reason=reason)
                return [self._empty_graph_with_meta(
                    status="UNSAT", alpha_bound=alpha, d_max_bound=d_max,
                    pruned_by=rule, pruned_reason=reason,
                    time_limit_s=self.time_limit_s, wall_time_s=0.0,
                )]

        # Build base CNF using SATKissat's exporter, sans edge_lex
        # (we'll branch on row-0 instead).
        builder = SATKissat(
            self.n, alpha=alpha, d_max=d_max,
            time_limit_s=self.time_limit_s,
            ramsey_prune=False,
            edge_lex=self.edge_lex,
            degree_encoding=self.degree_encoding,
        )
        cnf_text, var_idx = builder._build_dimacs()
        edge_of = {v: ij for ij, v in var_idx.items()}

        # Choose branching variables: the first `cube_depth` row-0 edges.
        cube_depth = min(self.cube_depth, n - 1)
        branch_vars = [var_idx[(0, j + 1)] for j in range(cube_depth)]
        # Edge_lex on row 0 forbids "0 then 1" patterns; under lex,
        # the only valid row-0 prefixes are the monotone ones (k 1s
        # followed by (cube_depth - k) 0s). That's cube_depth + 1
        # cubes, not 2^cube_depth — much more balanced.
        if self.edge_lex:
            cubes = []
            for k in range(cube_depth + 1):
                cube = tuple([+v for v in branch_vars[:k]] +
                             [-v for v in branch_vars[k:]])
                cubes.append(cube)
        else:
            cubes = [tuple(s * v for s, v in zip(signs, branch_vars))
                     for signs in product((+1, -1), repeat=cube_depth)]

        n_workers = self.n_workers or min(len(cubes), os.cpu_count() or 4)
        kissat_path = self.kissat_path or shutil.which("kissat")
        if not kissat_path:
            raise FileNotFoundError("kissat not on PATH; run setup_kissat.sh")

        self._log("cnc_start", n_cubes=len(cubes), n_workers=n_workers,
                  cube_depth=cube_depth, branch_vars=branch_vars)

        # Persist the base CNF to a temp file so workers can read it.
        with tempfile.NamedTemporaryFile("w", suffix=".cnf",
                                         delete=False) as fh:
            fh.write(cnf_text)
            base_cnf = fh.name

        # Launch up to n_workers kissat subprocesses concurrently;
        # poll, collect, kill survivors when SAT lands or when the
        # global budget expires.
        t0 = time.monotonic()
        completed: list[dict] = []
        winner_sat: dict | None = None

        def _spawn(cube: tuple[int, ...]) -> dict:
            cube_cnf = _write_cube_cnf(base_cnf, cube)
            log_fd, log_path = tempfile.mkstemp(suffix=".log")
            cmd = [kissat_path,
                   f"--time={int(max(1, self.cube_time_limit_s))}",
                   *self.extra_args, cube_cnf]
            # Route stdout to a file so kissat's verbose output never
            # fills the PIPE buffer and deadlocks the subprocess.
            proc = subprocess.Popen(
                cmd, stdout=log_fd, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            os.close(log_fd)  # Popen dup'd it; we just need the path
            return {"cube": cube, "cnf": cube_cnf, "log": log_path,
                    "proc": proc, "t0": time.monotonic()}

        running: list[dict] = []
        pending = list(cubes)

        try:
            # Prime the pool.
            while pending and len(running) < n_workers:
                running.append(_spawn(pending.pop(0)))

            while running and winner_sat is None:
                if time.monotonic() - t0 >= self.time_limit_s:
                    break
                still: list[dict] = []
                for r in running:
                    rc = r["proc"].poll()
                    if rc is None:
                        still.append(r)
                        continue
                    try:
                        with open(r["log"]) as fh:
                            stdout = fh.read()
                    except OSError:
                        stdout = ""
                    status, true_vars = _parse_kissat_stdout(stdout)
                    wall = time.monotonic() - r["t0"]
                    res = {"status": status, "wall": wall,
                           "true_vars": true_vars, "cube": r["cube"]}
                    completed.append(res)
                    self._log("cube_done", status=status,
                              wall=round(wall, 3), cube=r["cube"])
                    for path_key in ("cnf", "log"):
                        try: os.unlink(r[path_key])
                        except OSError: pass
                    if status == "SAT":
                        winner_sat = res
                        break
                    # Refill from pending.
                    if pending:
                        still.append(_spawn(pending.pop(0)))
                running = still
                if winner_sat is None and running:
                    time.sleep(0.05)

            # Kill any survivors.
            for r in running:
                try:
                    os.killpg(os.getpgid(r["proc"].pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
                try: r["proc"].wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    try: os.killpg(os.getpgid(r["proc"].pid), signal.SIGKILL)
                    except (ProcessLookupError, PermissionError): pass
                for path_key in ("cnf", "log"):
                    try: os.unlink(r[path_key])
                    except OSError: pass
        finally:
            try: os.unlink(base_cnf)
            except OSError: pass

        wall = round(time.monotonic() - t0, 4)

        if winner_sat is not None:
            verdict = "SAT"
            G = nx.Graph()
            G.add_nodes_from(range(n))
            for v in winner_sat["true_vars"]:
                ij = edge_of.get(v)
                if ij is not None:
                    G.add_edge(*ij)
        elif all(c["status"] == "UNSAT" for c in completed) and len(completed) == len(cubes):
            verdict = "UNSAT"
            G = nx.Graph()
            G.add_nodes_from(range(n))
        else:
            verdict = "TIMED_OUT"
            G = nx.Graph()
            G.add_nodes_from(range(n))

        self._stamp(G)
        G.graph["metadata"] = {
            "status":          verdict,
            "alpha_bound":     alpha,
            "d_max_bound":     d_max,
            "time_limit_s":    self.time_limit_s,
            "wall_time_s":     wall,
            "n_cubes":         len(cubes),
            "n_workers":       n_workers,
            "cube_walls":      [round(c["wall"], 3) for c in completed],
            "cube_statuses":   [c["status"] for c in completed],
        }
        return [G]
