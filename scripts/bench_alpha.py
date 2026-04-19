#!/usr/bin/env python3
"""
scripts/bench_alpha.py
======================
Head-to-head bench for the two exact α solvers:

    alpha_exact (bitmask B&B)   vs   alpha_cpsat (OR-Tools CP-SAT, x[0]=1 pin)

Runs both on one K4-free circulant per target n, pulled from
graphs/circulant_fast.json. Records wall time and child peak RSS (via
resource.getrusage in a forked subprocess, so RSS is per-solver, not
cumulative). B&B gets a per-call wall-clock timeout so the script
doesn't hang — default 60 s matches the CP-SAT limit.

Usage::

    micromamba run -n k4free python scripts/bench_alpha.py
    micromamba run -n k4free python scripts/bench_alpha.py --ns 20,30,40,50,60 --timeout 30
"""

import argparse
import json
import multiprocessing as mp
import os
import resource
import sys
import time

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from utils.graph_props import alpha_cpsat, alpha_exact


def _run_solver(solver_name: str, adj_bytes: bytes, shape: tuple, timeout: float, q: mp.Queue):
    adj = np.frombuffer(adj_bytes, dtype=np.uint8).reshape(shape)
    t0 = time.monotonic()
    if solver_name == "bb":
        alpha, _ = alpha_exact(adj)
    elif solver_name == "cpsat":
        alpha, _ = alpha_cpsat(adj, time_limit=timeout, vertex_transitive=True)
    else:
        raise ValueError(solver_name)
    dt = time.monotonic() - t0
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    q.put((alpha, dt, rss_kb))


def _timed(solver: str, adj: np.ndarray, timeout: float) -> tuple[int | None, float, int]:
    ctx = mp.get_context("fork")
    q: mp.Queue = ctx.Queue()
    p = ctx.Process(
        target=_run_solver,
        args=(solver, adj.tobytes(), adj.shape, timeout, q),
    )
    p.start()
    p.join(timeout + 5.0)
    if p.is_alive():
        p.terminate()
        p.join(2.0)
        if p.is_alive():
            p.kill()
        return None, timeout, -1
    if q.empty():
        return None, -1.0, -1
    alpha, dt, rss_kb = q.get()
    return alpha, dt, rss_kb


def _load_candidates(db_path: str, ns: list[int]) -> dict[int, nx.Graph]:
    with open(db_path) as f:
        db = json.load(f)
    by_n: dict[int, nx.Graph] = {}
    for entry in db:
        G = nx.from_sparse6_bytes(entry["sparse6"].encode())
        n = G.number_of_nodes()
        if n in ns and n not in by_n:
            by_n[n] = G
    return by_n


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ns", default="20,30,40,50,60,70,80",
                   help="Comma-separated list of n values to bench.")
    p.add_argument("--timeout", type=float, default=60.0,
                   help="Per-solver wall-clock timeout in seconds (default 60).")
    p.add_argument("--db", default=os.path.join(REPO, "graphs", "circulant_fast.json"))
    args = p.parse_args()

    ns = [int(x) for x in args.ns.split(",")]
    graphs = _load_candidates(args.db, ns)

    missing = [n for n in ns if n not in graphs]
    if missing:
        print(f"!! no circulant_fast entry for n ∈ {missing}; run "
              f"scripts/run_circulant_fast.py --save first.")
    ns = [n for n in ns if n in graphs]

    print(f"{'n':>4}  {'solver':>7}  {'α':>4}  {'wall (s)':>10}  {'peak RSS (MB)':>14}")
    print("-" * 50)
    for n in sorted(ns):
        G = graphs[n]
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        for solver in ("bb", "cpsat"):
            alpha, dt, rss_kb = _timed(solver, adj, args.timeout)
            rss_mb = rss_kb / 1024.0 if rss_kb > 0 else float("nan")
            if alpha is None:
                print(f"{n:>4}  {solver:>7}  {'—':>4}  {'timeout':>10}  {rss_mb:>14.1f}")
            else:
                print(f"{n:>4}  {solver:>7}  {alpha:>4}  {dt:>10.3f}  {rss_mb:>14.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
