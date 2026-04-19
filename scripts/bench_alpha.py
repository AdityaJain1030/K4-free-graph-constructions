#!/usr/bin/env python3
"""
scripts/bench_alpha.py
======================
Head-to-head bench for every exact α solver in utils.graph_props.

Solvers benchmarked:
    alpha_exact              — pure-Python bitmask B&B (baseline)
    alpha_bb_clique_cover    — B&B with greedy clique-cover bound
    alpha_bb_numba           — Numba-jitted bitmask B&B
    alpha_cpsat              — OR-Tools CP-SAT
    alpha_cpsat (VT pin)     — same, x[0]=1 (sound on circulants)
    alpha_maxsat             — python-sat RC2 MaxSAT
    alpha_clique_complement  — Bron–Kerbosch max clique on complement

Inputs are sparse K4-free circulants. By default each n uses
C(n, {1, 2}) — 4-regular, K4-free for n ≥ 6, α = ⌊n/3⌋ exactly. Pass
--family to choose other generators (e.g. "124" for C(n, {1, 2, 4}),
6-regular when K4-free).

Each solver runs in a forked subprocess so its peak RSS is recorded
independently (via resource.getrusage) and a timeout aborts hung runs
without hanging the driver.

Usage::

    micromamba run -n k4free python scripts/bench_alpha.py
    micromamba run -n k4free python scripts/bench_alpha.py --ns 20,40,60,80,100,150,200,300 --timeout 120
"""

import argparse
import multiprocessing as mp
import os
import resource
import sys
import time

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


SOLVERS = [
    "exact",
    "bb_clique_cover",
    "bb_numba",
    "cpsat",
    "cpsat_vt",
    "maxsat",
    "clique_complement",
]


def _run_solver(solver_name: str, adj_bytes: bytes, shape: tuple,
                timeout: float, q: mp.Queue) -> None:
    # imports inside child so JIT-compile cost shows up in that process only
    from utils.graph_props import (
        alpha_bb_clique_cover,
        alpha_bb_numba,
        alpha_clique_complement,
        alpha_cpsat,
        alpha_exact,
        alpha_maxsat,
    )

    adj = np.frombuffer(adj_bytes, dtype=np.uint8).reshape(shape)
    t0 = time.monotonic()
    if solver_name == "exact":
        alpha, _ = alpha_exact(adj)
    elif solver_name == "bb_clique_cover":
        alpha, _ = alpha_bb_clique_cover(adj)
    elif solver_name == "bb_numba":
        alpha, _ = alpha_bb_numba(adj)
    elif solver_name == "cpsat":
        alpha, _ = alpha_cpsat(adj, time_limit=timeout, vertex_transitive=False)
    elif solver_name == "cpsat_vt":
        alpha, _ = alpha_cpsat(adj, time_limit=timeout, vertex_transitive=True)
    elif solver_name == "maxsat":
        alpha, _ = alpha_maxsat(adj)
    elif solver_name == "clique_complement":
        alpha, _ = alpha_clique_complement(adj)
    else:
        raise ValueError(solver_name)
    dt = time.monotonic() - t0
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    q.put((int(alpha), dt, rss_kb))


def _timed(solver: str, adj: np.ndarray, timeout: float) -> tuple[int | None, float, int]:
    ctx = mp.get_context("fork")
    q: mp.Queue = ctx.Queue()
    p = ctx.Process(
        target=_run_solver,
        args=(solver, adj.tobytes(), adj.shape, timeout, q),
    )
    p.start()
    p.join(timeout + 10.0)
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


FAMILY_JUMPS: dict[str, list[int]] = {
    "12":   [1, 2],          # 4-regular, K4-free for n ≥ 6
    "13":   [1, 3],          # 4-regular, K4-free
    "124":  [1, 2, 4],       # 6-regular, K4-free for most n
    "1248": [1, 2, 4, 8],    # 8-regular, Paley-style, K4-free for many n
}


def _construct(n: int, family: str) -> nx.Graph | None:
    """Build a circulant in the named family. Returns None if not K4-free."""
    from utils.graph_props import is_k4_free_nx
    jumps = FAMILY_JUMPS[family]
    jumps = [j for j in jumps if 1 <= j <= n // 2]
    if not jumps:
        return None
    G = nx.circulant_graph(n, jumps)
    return G if is_k4_free_nx(G) else None


def _collect_inputs(ns: list[int], family: str) -> dict[int, tuple[nx.Graph, str]]:
    out: dict[int, tuple[nx.Graph, str]] = {}
    for n in ns:
        G = _construct(n, family)
        if G is None:
            print(f"!! C({n}, {FAMILY_JUMPS[family]}) not K4-free, skipping",
                  file=sys.stderr)
            continue
        out[n] = (G, f"C(n,{FAMILY_JUMPS[family]})")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ns", default="20,40,60,80,100,150,200,250,300",
                   help="Comma-separated n values to bench.")
    p.add_argument("--timeout", type=float, default=60.0,
                   help="Per-solver wall-clock timeout in seconds.")
    p.add_argument("--solvers", default=",".join(SOLVERS),
                   help=f"Comma-separated solver list. Available: {SOLVERS}")
    p.add_argument("--family", default="12",
                   choices=sorted(FAMILY_JUMPS.keys()),
                   help="Circulant family to bench (default 12 = C(n,{1,2})).")
    p.add_argument("--warmup-numba", action="store_true",
                   help="Run bb_numba once on a tiny graph first to amortise JIT cost.")
    args = p.parse_args()

    ns = sorted({int(x) for x in args.ns.split(",")})
    solvers = [s.strip() for s in args.solvers.split(",")]
    inputs = _collect_inputs(ns, args.family)

    missing = [n for n in ns if n not in inputs]
    if missing:
        print(f"skipped n ∈ {missing}")
    ns = [n for n in ns if n in inputs]

    if args.warmup_numba and "bb_numba" in solvers:
        print("# warming numba JIT cache…", flush=True)
        adj_tiny = np.array(nx.to_numpy_array(nx.cycle_graph(5), dtype=np.uint8))
        _timed("bb_numba", adj_tiny, 30.0)

    print(f"# timeout {args.timeout}s, solvers={solvers}", flush=True)
    print(f"{'n':>4}  {'src':>10}  {'solver':>18}  {'α':>5}  "
          f"{'wall (s)':>10}  {'peak RSS (MB)':>14}", flush=True)
    print("-" * 72, flush=True)

    results: list[dict] = []
    for n in ns:
        G, src = inputs[n]
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        alphas_seen = set()
        for solver in solvers:
            alpha, dt, rss_kb = _timed(solver, adj, args.timeout)
            rss_mb = rss_kb / 1024.0 if rss_kb > 0 else float("nan")
            if alpha is None:
                print(f"{n:>4}  {src:>10}  {solver:>18}  {'—':>5}  "
                      f"{'timeout':>10}  {rss_mb:>14.1f}", flush=True)
            else:
                alphas_seen.add(alpha)
                print(f"{n:>4}  {src:>10}  {solver:>18}  {alpha:>5}  "
                      f"{dt:>10.3f}  {rss_mb:>14.1f}", flush=True)
            results.append({
                "n": n, "src": src, "solver": solver,
                "alpha": alpha, "wall_s": dt, "rss_mb": rss_mb,
            })
        if len(alphas_seen - {0}) > 1:
            print(f"!! disagreement at n={n}: alphas={alphas_seen}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
