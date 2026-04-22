#!/usr/bin/env python3
"""
scripts/asymmetric_lift_tabu.py
===============================
Tabu search over edge perturbations of the 2-lift of P(17).

Modes:

  --mode cross   289-bit neighborhood: only cross-layer edges (i, 17+j)
                 for i,j in 0..16. Warm start: no cross edges (base =
                 disjoint union 2·P(17), c=0.6789).

  --mode full    561-bit neighborhood: every edge in the 34-vertex
                 graph. Warm start: x = indicator of 2·P(17) edges,
                 so flipping allows both addition of new edges and
                 removal of existing P(17) edges.

Score is c(G) = α(G)·d_max(G) / (34·ln d_max(G)); non-K₄-free or d<2
scores +∞. Tabu list is last `tabu_len` flipped bit indices. Best-
neighbor move (may worsen) to escape local minima.

Any improving K₄-free construction with c < 0.70 is persisted to
graph_db under source='asymmetric_lift_tabu' with mode metadata.

Run::

    micromamba run -n k4free python scripts/asymmetric_lift_tabu.py \\
        --mode full --n-iters 300 --n-restarts 5 --time-limit 1800 --save-db
"""

from __future__ import annotations

import argparse
import math
import os
import random
import sys
import time
from collections import deque

import networkx as nx
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DEFAULT_GRAPHS, GraphStore
from utils.graph_props import alpha_bb_clique_cover, is_k4_free


P17_QR = frozenset({1, 2, 4, 8, 9, 13, 15, 16})
N_VERT = 34
NVAR_CROSS = 17 * 17                           # 289
NVAR_FULL = N_VERT * (N_VERT - 1) // 2          # 561
C_P17 = 3 * 8 / (17 * math.log(8))              # 0.678915...

# Precomputed edge-pair list for full mode.
_FULL_PAIRS = [(i, j) for i in range(N_VERT) for j in range(i + 1, N_VERT)]


def _build_two_copies_of_p17() -> np.ndarray:
    """34x34 adjacency matrix of the disjoint union 2·P(17)."""
    A = np.zeros((N_VERT, N_VERT), dtype=np.uint8)
    for c in range(2):
        off = 17 * c
        for i in range(17):
            for j in range(17):
                if i != j and (i - j) % 17 in P17_QR:
                    A[off + i, off + j] = 1
    return A


def _initial_adj_and_x(mode: str) -> tuple[np.ndarray, np.ndarray]:
    """Return (adj, x) for the warm start of `mode`.

    - 'cross': adj = 2·P(17), x = zeros(289) (no cross edges yet).
    - 'full':  adj = 2·P(17), x = indicator of 2·P(17)'s edges (length 561).
    """
    adj = _build_two_copies_of_p17()
    if mode == "cross":
        x = np.zeros(NVAR_CROSS, dtype=np.uint8)
    elif mode == "full":
        x = np.zeros(NVAR_FULL, dtype=np.uint8)
        for k, (i, j) in enumerate(_FULL_PAIRS):
            if adj[i, j]:
                x[k] = 1
    else:
        raise ValueError(f"unknown mode {mode!r}")
    return adj, x


def _bit_to_edge(mode: str, k: int) -> tuple[int, int]:
    """Map bit index k to edge endpoints (i, j), i < j."""
    if mode == "cross":
        i = k // 17
        j = 17 + (k % 17)
        return (i, j) if i < j else (j, i)
    return _FULL_PAIRS[k]


def score(adj: np.ndarray) -> tuple[float, int, int]:
    """Return (c, alpha, d_max). c = +inf if K₄-present or d<2."""
    d = int(adj.sum(axis=1).max())
    if d < 2:
        return math.inf, 0, d
    if not is_k4_free(adj):
        return math.inf, 0, d
    alpha, _ = alpha_bb_clique_cover(adj)
    return alpha * d / (N_VERT * math.log(d)), int(alpha), d


def _save_record(store: GraphStore, adj: np.ndarray, c: float, a: int, d: int,
                 x: np.ndarray, *, mode: str, context: str) -> bool:
    """Persist one graph record under source='asymmetric_lift_tabu'."""
    G = nx.from_numpy_array(np.asarray(adj, dtype=np.uint8))
    n_edges = int(np.asarray(adj).sum()) // 2
    # Base edge count of 2·P(17) is 136. Deltas are informative.
    meta: dict = {
        "n": N_VERT,
        "alpha": int(a),
        "d_max": int(d),
        "c_log": float(c),
        "base_construction": "disjoint union of 2·P(17)",
        "tabu_mode": mode,
        "n_edges": n_edges,
        "n_edges_vs_2P17": n_edges - 136,
        "context": context,
    }
    if mode == "cross":
        cross_edges = [(int(i), int(17 + j))
                       for i in range(17) for j in range(17)
                       if x[17 * i + j]]
        meta["cross_layer_edges"] = cross_edges
        meta["n_cross_edges"] = len(cross_edges)
    _, is_new = store.add_graph(
        G, source="asymmetric_lift_tabu",
        filename="asymmetric_lift_tabu.json", **meta,
    )
    return is_new


def _toggle_edge(adj: np.ndarray, k: int, mode: str) -> tuple[int, int]:
    """Toggle one edge in-place; return (i, j)."""
    i, j = _bit_to_edge(mode, k)
    adj[i, j] ^= 1
    adj[j, i] ^= 1
    return i, j


def tabu_run(*, mode: str, n_iters: int, tabu_len: int, n_restarts: int,
             seed: int, time_limit_s: float, save_db: bool,
             diversify_bits: int = 6, verbosity: int = 1):
    random.seed(seed)
    np.random.seed(seed)
    nvar = NVAR_CROSS if mode == "cross" else NVAR_FULL

    store = GraphStore(DEFAULT_GRAPHS) if save_db else None

    # Sanity baseline.
    adj0, x0 = _initial_adj_and_x(mode)
    c0, a0, d0 = score(adj0)
    if verbosity:
        print(f"[base] 2·P(17) ({mode}-mode): c={c0:.6f} "
              f"(expect {C_P17:.6f}), α={a0}, d={d0}",
              flush=True)

    # Start global best at the true base (not dummy zeros).
    global_best = (c0, a0, d0, x0.copy())
    t_start = time.monotonic()

    for r in range(n_restarts):
        adj, x = _initial_adj_and_x(mode)
        if r > 0:
            k_start = random.randint(1, diversify_bits)
            for k in random.sample(range(nvar), k_start):
                _toggle_edge(adj, k, mode)
                x[k] ^= 1

        c_cur, a_cur, d_cur = score(adj)
        run_best = (c_cur, a_cur, d_cur, x.copy())
        tabu: deque[int] = deque(maxlen=tabu_len)

        if verbosity:
            k4 = "K4-free" if c_cur < math.inf else "K4-HIT"
            print(f"[restart {r}] start c={c_cur:.6f} ({k4})", flush=True)

        for it in range(n_iters):
            if time.monotonic() - t_start > time_limit_s:
                if verbosity:
                    print(f"[restart {r}] time budget exhausted at iter {it}",
                          flush=True)
                break

            best_flip = (math.inf, 0, 0, -1)  # (c, alpha, d, bit)
            for k in range(nvar):
                if k in tabu:
                    continue
                i, j = _toggle_edge(adj, k, mode)
                c_new, a_new, d_new = score(adj)
                # Revert.
                adj[i, j] ^= 1
                adj[j, i] ^= 1
                if c_new < best_flip[0]:
                    best_flip = (c_new, a_new, d_new, k)

            if best_flip[3] < 0:
                break

            c_cur, a_cur, d_cur, k = best_flip
            _toggle_edge(adj, k, mode)
            x[k] ^= 1
            tabu.append(k)

            if c_cur < run_best[0] - 1e-9:
                run_best = (c_cur, a_cur, d_cur, x.copy())
                n_edges = int(np.asarray(adj).sum()) // 2
                if verbosity:
                    print(f"[restart {r} iter {it:>3}] new best "
                          f"c={c_cur:.6f} α={a_cur} d={d_cur} "
                          f"n_edges={n_edges} (Δ={n_edges - 136:+d})",
                          flush=True)

        if run_best[0] < global_best[0] - 1e-9:
            global_best = run_best
            c, a, d, x_b = run_best
            # Rebuild adj for saving: start from base then apply x's toggles.
            if save_db and store is not None and c < 0.70 and c < math.inf:
                adj_b, _ = _initial_adj_and_x(mode)
                if mode == "cross":
                    for k in range(NVAR_CROSS):
                        if x_b[k]:
                            _toggle_edge(adj_b, k, mode)
                else:
                    # In full mode, x_b IS the adjacency indicator; rebuild.
                    adj_b = np.zeros((N_VERT, N_VERT), dtype=np.uint8)
                    for k, (i, j) in enumerate(_FULL_PAIRS):
                        if x_b[k]:
                            adj_b[i, j] = 1
                            adj_b[j, i] = 1
                is_new = _save_record(
                    store, adj_b, c, a, d, x_b,
                    mode=mode,
                    context=f"restart {r}, global new best",
                )
                if verbosity:
                    print(f"[DB] {'saved' if is_new else 'already present'} "
                          f"c={c:.6f}", flush=True)

    elapsed = time.monotonic() - t_start
    c, a, d, x_b = global_best
    n_edges_final = 136
    if mode == "full":
        n_edges_final = int(x_b.sum())
    else:
        n_edges_final = 136 + int(x_b.sum())
    print(f"\n=== final ({mode}) ===")
    print(f"best c = {c:.6f} (α={a}, d={d}, n_edges={n_edges_final}, "
          f"Δ_vs_2P17={n_edges_final - 136:+d})")
    print(f"reference c(P(17)) = {C_P17:.6f}")
    if c < C_P17 - 1e-9:
        print(f"*** BEATS P(17) by {C_P17 - c:.6f} ***")
    elif abs(c - C_P17) < 1e-9:
        if mode == "full" and int(x_b.sum()) == 136:
            print("tied with P(17) (returned to 2·P(17) — no improvement found)")
        elif mode == "cross" and int(x_b.sum()) == 0:
            print("tied with P(17) (no cross edges added — no improvement found)")
        else:
            print("tied with P(17) at a DIFFERENT graph (non-VT c-floor match)")
    else:
        print(f"did not beat P(17) (Δ = +{c - C_P17:.6f})")
    print(f"elapsed: {elapsed:.1f}s")

    return global_best


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("cross", "full"), default="full")
    ap.add_argument("--n-iters", type=int, default=300)
    ap.add_argument("--n-restarts", type=int, default=5)
    ap.add_argument("--tabu-len", type=int, default=100)
    ap.add_argument("--time-limit", type=float, default=1800.0)
    ap.add_argument("--seed", type=int, default=20260421)
    ap.add_argument("--diversify-bits", type=int, default=6,
                    help="Max number of random bit flips for restart "
                         "diversification (r > 0).")
    ap.add_argument("--save-db", action="store_true")
    ap.add_argument("--verbosity", type=int, default=1)
    args = ap.parse_args()

    tabu_run(
        mode=args.mode,
        n_iters=args.n_iters,
        tabu_len=args.tabu_len,
        n_restarts=args.n_restarts,
        seed=args.seed,
        time_limit_s=args.time_limit,
        save_db=args.save_db,
        diversify_bits=args.diversify_bits,
        verbosity=args.verbosity,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
