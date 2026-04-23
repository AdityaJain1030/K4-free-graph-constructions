#!/usr/bin/env python3
"""
scripts/run_polarity_extended.py
=================================
Build Erdős–Rényi polarity graphs ER(q) for prime AND prime-power q.

For prime q the existing `PolaritySearch` is reused via the Search
base class (compute α, c_log, ingest under source='polarity'). For
prime-power q the construction is done here directly against
`search._fq.field` and ingested the same way.

Every ER(q) is:
  * on N = q² + q + 1 vertices (projective points of PG(2, q))
  * (q+1)-regular except at q+1 absolute points (degree q)
  * C₄-free (and therefore K₄-free)

Usage:
    python scripts/run_polarity_extended.py --qs 8 9 11 13 16 17 19 23
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from math import log

import numpy as np
import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from search._fq import field, _is_prime, _prime_power
from utils.graph_props import is_k4_free_nx, alpha_bb_clique_cover, alpha_cpsat
from utils.alpha_surrogate import alpha_lb
from graph_db import GraphStore, DEFAULT_GRAPHS, DB


# ---------------------------------------------------------------------------
# Polarity graph over F_q for any prime power q
# ---------------------------------------------------------------------------


def _pg2_points(F):
    """Canonical projective-plane points over F_q. First non-zero coord = 1."""
    pts = [(F.zero, F.zero, F.one)]
    for c in F.elements():
        pts.append((F.zero, F.one, c))
    for b in F.elements():
        for c in F.elements():
            pts.append((F.one, b, c))
    return pts


def _build_er_polarity(q: int) -> nx.Graph:
    F = field(q)
    pts = _pg2_points(F)
    n = len(pts)
    G = nx.Graph()
    G.add_nodes_from(range(n))
    for i in range(n):
        pi = pts[i]
        for j in range(i + 1, n):
            pj = pts[j]
            dot = F.add(F.add(F.mul(pi[0], pj[0]), F.mul(pi[1], pj[1])), F.mul(pi[2], pj[2]))
            if dot == F.zero:
                G.add_edge(i, j)
    # Self-loops (absolute points) shouldn't be added since i != j, but be safe.
    G.remove_edges_from(nx.selfloop_edges(G))
    return G


# ---------------------------------------------------------------------------
# Property compute + ingest
# ---------------------------------------------------------------------------


def _analyze(G: nx.Graph):
    n = G.number_of_nodes()
    deg = [d for _, d in G.degree()]
    d_max = max(deg)
    d_min = min(deg)
    A = nx.to_numpy_array(G, dtype=float)
    eigs = np.linalg.eigvalsh(A)
    lam_max, lam_min = float(eigs.max()), float(eigs.min())
    H = n * (-lam_min) / (d_max - lam_min) if d_max != lam_min else float("inf")
    return dict(n=n, d_max=d_max, d_min=d_min,
                lambda_max=lam_max, lambda_min=lam_min, hoffman=H)


def _alpha_exact(G: nx.Graph, cap_seconds: float):
    """α via CP-SAT in a subprocess with a hard wall-clock kill.

    `alpha_cpsat` takes a `time_limit` but OR-Tools presolve can run
    far longer on non-vertex-transitive polarity graphs. Use a real
    subprocess + signal timeout so we never hang.
    """
    import multiprocessing as mp

    adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
    t0 = time.monotonic()

    def _worker(adj, time_limit, q):
        from utils.graph_props import alpha_cpsat as _alpha
        a, _ = _alpha(adj, time_limit=time_limit, vertex_transitive=False)
        q.put(int(a))

    q_out: "mp.Queue[int]" = mp.Queue()
    proc = mp.Process(target=_worker, args=(adj, cap_seconds, q_out))
    proc.start()
    proc.join(timeout=cap_seconds + 5.0)
    if proc.is_alive():
        proc.terminate()
        proc.join(5.0)
        if proc.is_alive():
            proc.kill()
    dt = time.monotonic() - t0
    try:
        a = q_out.get_nowait()
    except Exception:
        a = 0
    if a > 0:
        return int(a), dt, True
    lb = alpha_lb(adj, restarts=64)
    return int(lb), dt, False


def run_for_q(q: int, alpha_timeout_s: float, force: bool) -> dict | None:
    print(f"\n=== ER polarity, q={q} ===", flush=True)
    N = q * q + q + 1
    print(f"  expected N = q^2+q+1 = {N}", flush=True)

    t0 = time.monotonic()
    G = _build_er_polarity(q)
    build_s = time.monotonic() - t0
    n = G.number_of_nodes()
    m = G.number_of_edges()
    print(f"  built: n={n}  m={m}  ({build_s:.2f}s)", flush=True)
    assert n == N, f"vertex count mismatch: {n} vs {N}"

    k4_free = is_k4_free_nx(G)
    print(f"  K4-free: {k4_free}", flush=True)
    if not k4_free:
        print("  ^^^ not K4-free, skipping (shouldn't happen for ER)", flush=True)
        return None

    props = _analyze(G)
    print(f"  d_max={props['d_max']}  d_min={props['d_min']}  "
          f"λ_min={props['lambda_min']:.4f}  H={props['hoffman']:.4f}", flush=True)

    # α via CP-SAT (with timeout)
    print(f"  computing α via CP-SAT (cap {alpha_timeout_s:.0f}s)...", flush=True)
    alpha_val, alpha_s, exact = _alpha_exact(G, alpha_timeout_s)
    c_log = alpha_val * props["d_max"] / (props["n"] * log(props["d_max"]))
    ratio = alpha_val / props["hoffman"] if props["hoffman"] > 0 else float("nan")
    flag = "exact" if exact else "LB (CP-SAT timed out)"
    print(f"  α={alpha_val} [{flag}]  c_log={c_log:.6f}  α/H={ratio:.4f}  "
          f"(α solve {alpha_s:.1f}s)", flush=True)

    # Ingest
    store = GraphStore(DEFAULT_GRAPHS)
    gid, was_new = store.add_graph(
        G, source="polarity",
        filename="polarity.json",
        q=int(q),
        construction="erdos_renyi_polarity",
        q_is_prime_power=_prime_power(q) is not None and not _is_prime(q),
        alpha_exact=int(alpha_val),
        alpha_is_exact=bool(exact),
        d_max=int(props["d_max"]),
        c_log_exact=float(c_log),
        hoffman=float(props["hoffman"]),
        lambda_min=float(props["lambda_min"]),
        lambda_max=float(props["lambda_max"]),
    )
    tag = "new" if was_new else "dup"
    print(f"  [{tag}] graph_id={gid[:14]}", flush=True)

    return dict(
        q=q, n=props["n"], d_max=props["d_max"],
        alpha=alpha_val, c_log=c_log,
        H=props["hoffman"], lambda_min=props["lambda_min"],
        graph_id=gid, was_new=was_new,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--qs", type=int, nargs="+", required=True)
    ap.add_argument("--alpha-timeout-s", type=float, default=300.0)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    results = []
    for q in args.qs:
        r = run_for_q(q, args.alpha_timeout_s, args.force)
        if r:
            results.append(r)

    # Summary table + frontier comparison
    print("\n" + "=" * 88)
    print(f"{'q':>4}{'N':>5}{'α':>4}{'d_max':>7}{'c_log':>11}{'H':>9}{'α/H':>7}   vs frontier")
    print("=" * 88)
    with DB() as db:
        db.sync(verbose=True)
        # per-N best (excluding polarity itself)
        best_other = {}
        for r in db.query():
            if r.get('c_log') is None or r['source'] == 'polarity':
                continue
            nn = r['n']
            if nn not in best_other or r['c_log'] < best_other[nn]['c_log']:
                best_other[nn] = r

    for r in results:
        fr = best_other.get(r['n'])
        if fr is None:
            cmp = "NEW-N"
        elif r['c_log'] < fr['c_log'] - 1e-6:
            cmp = f"WIN (prev {fr['source']} {fr['c_log']:.4f})"
        elif abs(r['c_log'] - fr['c_log']) < 1e-6:
            cmp = f"TIE ({fr['source']})"
        else:
            cmp = f"loses to {fr['source']} by +{r['c_log']-fr['c_log']:.4f}"
        print(f"{r['q']:>4}{r['n']:>5}{r['alpha']:>4}{r['d_max']:>7}"
              f"{r['c_log']:>11.4f}{r['H']:>9.3f}{r['alpha']/r['H']:>7.3f}   {cmp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
