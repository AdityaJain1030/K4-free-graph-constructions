#!/usr/bin/env python3
"""
scripts/run_psl_tabu.py
========================
Tabu search on Cayley(PSL(2, q), S) over inversion orbits of S.

Mirrors `search.cayley_tabu` but for a single group (PSL(2, q)) built
via `search.groups_psl.psl2`. PSL orders are above the GAP
SmallGroups cap, so the GAP-backed sweep skips them.

Usage:
    python scripts/run_psl_tabu.py --q 8  --n-iters 200 --n-restarts 3
    python scripts/run_psl_tabu.py --q 11 --n-iters 200 --n-restarts 3
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

from search.groups_psl import psl2
from search.groups import cayley_adj_from_bitvec, connection_set_from_bitvec
from search.tabu import multi_restart_tabu, TabuResult
from utils.graph_props import is_k4_free, alpha_bb_clique_cover, alpha_cpsat
from utils.alpha_surrogate import alpha_lb

from graph_db import GraphStore, DEFAULT_GRAPHS, DB


def _adj_to_nx(adj):
    n = adj.shape[0]
    G = nx.Graph()
    G.add_nodes_from(range(n))
    iu, ju = np.where(np.triu(adj, 1))
    G.add_edges_from(zip(iu.tolist(), ju.tolist()))
    return G


def make_cost_fn(fam, rng, lb_restarts):
    n = fam.order

    def cost(bits):
        if not bits.any():
            return float("inf")
        adj = cayley_adj_from_bitvec(fam, bits)
        d_max = int(adj.sum(axis=1).max())
        if d_max <= 1:
            return float("inf")
        if not is_k4_free(adj):
            return float("inf")
        a_lb = alpha_lb(adj, restarts=lb_restarts, rng=rng)
        return a_lb * d_max / (n * log(d_max))

    return cost


def run_one(q: int, n_iters: int, n_restarts: int, tabu_len,
            lb_restarts: int, time_limit_s, seed: int, verbose: bool):
    print(f"\n=== PSL(2, {q}) ===", flush=True)
    t0 = time.monotonic()
    fam = psl2(q)
    print(f"  built GroupSpec: order={fam.order}  n_orbits={fam.n_orbits}  "
          f"(build {time.monotonic()-t0:.2f}s)", flush=True)

    L = fam.n_orbits
    rng = np.random.default_rng(seed)
    cost_fn = make_cost_fn(fam, rng, lb_restarts)

    # Progress-reporting cost wrapper
    eval_count = {"n": 0, "last_report": time.monotonic()}
    last_best = {"c": float("inf")}

    def cost_report(bits):
        c = cost_fn(bits)
        eval_count["n"] += 1
        if c < last_best["c"]:
            last_best["c"] = c
            d_max = int(cayley_adj_from_bitvec(fam, bits).sum(axis=1).max()) if np.isfinite(c) else -1
            print(f"    [eval {eval_count['n']}] surrogate c_log={c:.6f}  d={d_max}", flush=True)
        elif verbose and time.monotonic() - eval_count["last_report"] > 15.0:
            print(f"    [eval {eval_count['n']}] t={time.monotonic()-t0:.1f}s  "
                  f"best c={last_best['c']:.6f}", flush=True)
            eval_count["last_report"] = time.monotonic()
        return c

    print(f"  running multi_restart_tabu: L={L}, restarts={n_restarts}, "
          f"iters/restart={n_iters}, tabu_len={tabu_len}, "
          f"time_limit_s={time_limit_s}", flush=True)

    t_tabu = time.monotonic()
    res: TabuResult = multi_restart_tabu(
        L=L,
        cost=cost_report,
        n_restarts=n_restarts,
        n_iters=n_iters,
        tabu_len=tabu_len,
        rng=rng,
        time_limit_s=time_limit_s,
    )
    tabu_elapsed = time.monotonic() - t_tabu

    print(f"  tabu done in {tabu_elapsed:.1f}s  total_evals={eval_count['n']}", flush=True)
    print(f"  best surrogate c_log={res.best_cost}  best_iter={res.best_iter}  "
          f"n_iters={res.n_iters}", flush=True)

    if not np.isfinite(res.best_cost):
        print("  no feasible (K4-free, d>=2) state found — nothing to save", flush=True)
        return None

    # Build the winning graph
    adj = cayley_adj_from_bitvec(fam, res.best_state)
    if not is_k4_free(adj):
        print("  WARNING: best state no longer K4-free (cost fn bug?); skipping save",
              flush=True)
        return None

    # α via CP-SAT with time limit; PSL Cayley is vertex-transitive so pin x[0]=1
    print("  computing α via CP-SAT (vertex-transitive pin, 300s cap)...", flush=True)
    t_alpha = time.monotonic()
    alpha_exact, _mis = alpha_cpsat(adj, time_limit=300.0, vertex_transitive=True)
    if alpha_exact == 0:
        print("  CP-SAT did not prove optimum; falling back to α_lb", flush=True)
        alpha_exact = alpha_lb(adj, restarts=96)
        alpha_note = " (α_lb only — CP-SAT timed out)"
    else:
        alpha_note = ""
    d_max = int(adj.sum(axis=1).max())
    c_log_exact = alpha_exact * d_max / (fam.order * log(d_max))
    print(f"  alpha={alpha_exact}{alpha_note}  d_max={d_max}  c_log={c_log_exact:.6f}  "
          f"(alpha solve {time.monotonic()-t_alpha:.1f}s)", flush=True)

    # Spectrum -> Hoffman
    G = _adj_to_nx(adj)
    eigs = np.linalg.eigvalsh(nx.to_numpy_array(G, dtype=float))
    lam_min = float(eigs.min())
    H = fam.order * (-lam_min) / (d_max - lam_min)
    print(f"  λ_min={lam_min:.4f}  H={H:.4f}  α/H={alpha_exact/H:.4f}", flush=True)

    conn = connection_set_from_bitvec(fam, res.best_state)
    conn_serialisable = [
        [list(r) for r in s] if isinstance(s, tuple) and isinstance(s[0], tuple) else
        (list(s) if isinstance(s, tuple) else s)
        for s in conn
    ]

    # Ingest
    store = GraphStore(DEFAULT_GRAPHS)
    gid, was_new = store.add_graph(
        G, source="psl_tabu",
        filename="psl_tabu.json",
        group=fam.name,
        connection_set=conn_serialisable,
        connection_set_size=len(conn),
        surrogate_c_log=float(res.best_cost),
        alpha_exact=int(alpha_exact),
        d_max=int(d_max),
        c_log_exact=float(c_log_exact),
        hoffman=float(H),
        lambda_min=float(lam_min),
        tabu_n_iters=int(res.n_iters),
        tabu_best_iter=int(res.best_iter),
        tabu_elapsed_s=round(tabu_elapsed, 1),
    )
    tag = "new" if was_new else "dup"
    print(f"  [{tag}] graph_id={gid[:14]}  source='psl_tabu'", flush=True)
    return {
        "q": q, "n": fam.order, "d_max": d_max,
        "alpha": alpha_exact, "c_log": c_log_exact,
        "H": H, "lambda_min": lam_min,
        "graph_id": gid,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", type=int, required=True, help="prime-power for PSL(2, q)")
    ap.add_argument("--n-iters", type=int, default=200)
    ap.add_argument("--n-restarts", type=int, default=3)
    ap.add_argument("--tabu-len", type=int, default=None)
    ap.add_argument("--lb-restarts", type=int, default=16)
    ap.add_argument("--time-limit-s", type=float, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    result = run_one(
        args.q,
        n_iters=args.n_iters,
        n_restarts=args.n_restarts,
        tabu_len=args.tabu_len,
        lb_restarts=args.lb_restarts,
        time_limit_s=args.time_limit_s,
        seed=args.seed,
        verbose=not args.quiet,
    )

    if result is None:
        return 1
    # Sync cache so the row is queryable
    print("\nSyncing graph_db cache...", flush=True)
    with DB() as db:
        db.sync(verbose=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
