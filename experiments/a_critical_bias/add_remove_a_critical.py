#!/usr/bin/env python3
"""
experiments/a_critical_bias/add_remove_a_critical.py
=====================================================
Softmax K4-free add+remove walk where the candidate score combines a
c_log surrogate with an α-criticality structural penalty:

    energy(G) = c_log_surrogate(G) + λ · pen(G)
    score(m)  = -energy(G after m)

`pen` is the cheap structural surrogate from `penalties.py` (sum of
min-deg, twin-pair, and Hajnal violation counts). The walk is built on
EdgeFlipWalk; the only differences from `experiments/random/
add_remove_edges_weighted.py` are (a) the score function and (b) we
expose β=∞ (greedy) as a first-class option.

Stop modes (mirrored from the random/ drivers):
  edges --target T   halt when |E| >= T
  alpha --target T   halt when α(G) <= T  (CP-SAT every K steps)
  none               run until max_steps or saturation

Seeding modes:
  empty       (default) start from the empty graph
  from-db     pull current best non-SAT-derived graph at N from graph_db
  random-bk   uniform K4-free saturation fill (Bohman–Keevash)

Usage
-----
    # Single run, λ=1, β=4, alpha-stop at α=5, N=20
    python experiments/a_critical_bias/add_remove_a_critical.py \\
        --n 20 --lam 1.0 --beta 4 --stop alpha --target 5 --trials 3

    # Greedy run from the disjoint_lift seed at N=30
    python experiments/a_critical_bias/add_remove_a_critical.py \\
        --n 30 --lam 1.0 --beta inf --stop none --seed-graph from-db
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from typing import Callable

import networkx as nx
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from search import AggregateLogger
from search.stochastic_walk.edge_flip_walk import EdgeFlipWalk
from utils.alpha_surrogate import alpha_lb, c_log_surrogate
from utils.graph_props import alpha_cpsat

from penalties import surrogate_components, surrogate_penalty


# ── stop builders (same shape as random/) ─────────────────────────────────

def stop_edges(target):
    return lambda adj, info: int(adj.sum()) // 2 >= target


def stop_alpha(target, every=5):
    def f(adj, info):
        s = info.get("steps", 0)
        if s == 0 or s % every:
            return False
        a, _ = alpha_cpsat(adj, time_limit=10.0)
        return a > 0 and a <= target
    return f


STOP_BUILDERS: dict[str, Callable] = {"edges": stop_edges, "alpha": stop_alpha}


# ── proposer: full add+remove valid set ───────────────────────────────────

def propose_adds_and_removes(adj, valid_moves, info, rng, k):
    return valid_moves


# ── scorer ─────────────────────────────────────────────────────────────────

def make_score_fn(lam: float,
                  w_min_deg: float = 1.0,
                  w_twin: float = 1.0,
                  w_hajnal: float = 1.0,
                  lb_restarts: int = 4) -> Callable:
    """Return a batch_score_fn that ranks moves by -(c_log_surrogate +
    λ · structural_penalty) on the post-move graph."""

    def score(adj: np.ndarray, moves: list, info: dict) -> np.ndarray:
        rng = np.random.default_rng(int(info.get("steps", 0)))
        n_v = adj.shape[0]
        out = np.empty(len(moves), dtype=np.float64)
        work = adj.copy()
        deg = work.sum(axis=1).astype(np.int64)
        for i, (u, v, is_add) in enumerate(moves):
            prev = work[u, v]
            delta = 1 if is_add else -1
            work[u, v] = work[v, u] = 1 if is_add else 0
            deg[u] += delta
            deg[v] += delta
            # One α_lb call per candidate, shared between c_log and pen.
            a_lb = alpha_lb(work, restarts=lb_restarts, rng=rng)
            d_max = int(deg.max())
            if d_max <= 1:
                c = 100.0  # sentinel; let penalty drive early walk
            else:
                c = a_lb * d_max / (n_v * math.log(d_max))
            pen = surrogate_penalty(
                work,
                w_min_deg=w_min_deg, w_twin=w_twin, w_hajnal=w_hajnal,
                alpha=a_lb, rng=rng,
            )
            out[i] = -(c + lam * pen)
            work[u, v] = work[v, u] = prev
            deg[u] -= delta
            deg[v] -= delta
        return out

    return score


# ── seeding ────────────────────────────────────────────────────────────────

def _seed_from_db(n: int):
    """Best non-SAT-derived K4-free graph at N from graph_db, mirroring
    cluster_sat._seed_hint_graph. Returns nx.Graph or None."""
    try:
        import networkx as nx
        from graph_db import open_db, GraphStore, DEFAULT_GRAPHS
    except Exception:
        return None
    EXCLUDE = ("sat_exact", "sat_box", "server_sat_exact",
               "sat_circulant", "sat_circulant_optimal",
               "sat_regular", "sat_near_regular_nonreg")
    try:
        with open_db() as db:
            rows = db.top("c_log", k=20, ascending=True, n=n)
            r = next((row for row in rows
                      if row.get("source") not in EXCLUDE), None)
            if r is None:
                return None
            store = GraphStore(DEFAULT_GRAPHS)
            for rec in store.all_records():
                if rec.get("id") == r["graph_id"]:
                    return nx.from_sparse6_bytes(rec["sparse6"].encode())
    except Exception:
        return None
    return None


def _seed_random_bk(n: int, seed: int):
    """Uniform K4-free saturation fill (Bohman–Keevash). Returns adj."""
    rng = np.random.default_rng(seed)
    from utils.graph_props import adding_induces_k4
    adj = np.zeros((n, n), dtype=np.uint8)
    while True:
        cands = []
        for u in range(n):
            for v in range(u + 1, n):
                if not adj[u, v] and not adding_induces_k4(adj, u, v):
                    cands.append((u, v))
        if not cands:
            break
        u, v = cands[rng.integers(len(cands))]
        adj[u, v] = adj[v, u] = 1
    return adj


def _resolve_seed(args) -> "object | None":
    if args.seed_graph == "empty":
        return None
    if args.seed_graph == "from-db":
        g = _seed_from_db(args.n)
        if g is None:
            print(f"  WARN: from-db seeding failed (no graph at N={args.n}); "
                  "falling back to empty.", flush=True)
        return g
    if args.seed_graph == "random-bk":
        return _seed_random_bk(args.n, seed=args.seed)
    raise ValueError(f"unknown --seed-graph: {args.seed_graph}")


# ── post-run audit ─────────────────────────────────────────────────────────

def audit(adj: np.ndarray) -> dict:
    """Exact α + Lemma 4 vertex-local α-criticality test."""
    n = adj.shape[0]
    if n == 0 or int(adj.sum()) == 0:
        return {"alpha": 0, "is_a_critical": False, "n_non_critical_v": None}
    alpha, _ = alpha_cpsat(adj, time_limit=30.0)
    if alpha == 0:
        return {"alpha": None, "is_a_critical": False, "n_non_critical_v": None}
    n_bad = 0
    for v in range(n):
        keep = [u for u in range(n) if u != v and not adj[v, u]]
        if not keep:
            sub_alpha = 0
        else:
            sub = adj[np.ix_(keep, keep)]
            sub_alpha, _ = alpha_cpsat(sub, time_limit=15.0)
        if sub_alpha != alpha - 1:
            n_bad += 1
    return {
        "alpha": alpha,
        "is_a_critical": (n_bad == 0),
        "n_non_critical_v": n_bad,
    }


# ── runner ─────────────────────────────────────────────────────────────────

def _fmt(x): return "—" if x is None else f"{x:.4f}"


def _parse_beta(s: str) -> float:
    if s.lower() in ("inf", "infinity", "greedy"):
        return float("inf")
    return float(s)


def run(args) -> list[dict]:
    n = args.n
    stop_fn = None
    if args.stop != "none":
        stop_fn = STOP_BUILDERS[args.stop](int(args.target))
    score_fn = make_score_fn(
        lam=args.lam,
        w_min_deg=args.w_min_deg,
        w_twin=args.w_twin,
        w_hajnal=args.w_hajnal,
        lb_restarts=args.lb_restarts,
    )
    seed_graph = _resolve_seed(args)

    with AggregateLogger(name=f"a_critical_bias_lam{args.lam}") as agg:
        search = EdgeFlipWalk(
            n=n,
            stop_fn=stop_fn,
            propose_from_valid_moves_fn=propose_adds_and_removes,
            batch_score_fn=score_fn,
            beta=args.beta,
            top_k=max(1, args.trials),
            verbosity=0,
            parent_logger=agg,
            num_trials=args.trials,
            seed=args.seed,
            max_steps=args.max_steps if args.max_steps else 50 * n * n,
            max_consecutive_failures=5 * n * n,
            seed_graph=seed_graph,
        )
        results = search.run()
        if args.save and results:
            search.save([r for r in results if r.is_k4_free])

    rows: list[dict] = []
    if not results:
        print(f"[n={n}] no result")
        return rows

    print(f"\n  a_critical_bias  n={n}  lam={args.lam}  beta={args.beta}  "
          f"stop={args.stop}{'='+str(args.target) if args.stop!='none' else ''}  "
          f"seed_graph={args.seed_graph}  trials={args.trials}")
    print("  " + "-" * 78)
    for i, r in enumerate(results):
        adj = np.asarray(nx.to_numpy_array(r.G), dtype=np.uint8)
        comps = surrogate_components(adj)
        audit_info = {}
        if args.audit and r.is_k4_free:
            audit_info = audit(adj)
        added = r.metadata.get("added", 0)
        removed = r.metadata.get("removed", 0)
        print(f"  trial {i:>2}: c_log={_fmt(r.c_log)}  α={r.alpha:>3}  "
              f"d_max={r.d_max:>3}  |E|={r.metadata.get('edges', 0):>5}  "
              f"+{added}/-{removed}  "
              f"min_deg_v={comps.get('n_min_deg','-')}  "
              f"twin={comps.get('n_twin','-')}  "
              f"haj={comps.get('n_hajnal','-')}"
              + (f"  acrit={audit_info.get('is_a_critical')}  "
                 f"n_bad_v={audit_info.get('n_non_critical_v')}"
                 if audit_info else ""))
        rows.append({
            "n": n, "lam": args.lam, "beta": args.beta,
            "stop": args.stop, "target": args.target,
            "seed": args.seed + i, "seed_graph": args.seed_graph,
            "trial": i,
            "c_log": r.c_log, "alpha": r.alpha, "d_max": r.d_max,
            "edges": r.metadata.get("edges"),
            "added": added, "removed": removed,
            "n_min_deg": comps.get("n_min_deg"),
            "n_twin": comps.get("n_twin"),
            "n_hajnal": comps.get("n_hajnal"),
            "is_a_critical": audit_info.get("is_a_critical"),
            "n_non_critical_v": audit_info.get("n_non_critical_v"),
        })
    best = min(results, key=lambda r: r.c_log if r.c_log is not None else float("inf"))
    print(f"  best c_log = {_fmt(best.c_log)}")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--lam", type=float, default=1.0,
                    help="weight on the structural penalty (0 = no bias)")
    ap.add_argument("--beta", type=_parse_beta, default=4.0,
                    help="softmax temperature; pass 'inf' for greedy argmax")
    ap.add_argument("--stop", choices=list(STOP_BUILDERS) + ["none"],
                    default="none")
    ap.add_argument("--target", default=0)
    ap.add_argument("--seed-graph", choices=("empty", "from-db", "random-bk"),
                    default="empty")
    ap.add_argument("--w-min-deg", type=float, default=1.0)
    ap.add_argument("--w-twin",    type=float, default=1.0)
    ap.add_argument("--w-hajnal",  type=float, default=1.0)
    ap.add_argument("--lb-restarts", type=int, default=4)
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-steps", type=int, default=0)
    ap.add_argument("--save", action="store_true")
    ap.add_argument("--audit", action="store_true",
                    help="run exact α-criticality audit on each final graph")
    args = ap.parse_args()
    run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
