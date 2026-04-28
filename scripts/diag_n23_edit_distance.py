"""
scripts/diag_n23_edit_distance.py
==================================
How many edges separate the chain's best α=7 from the SAT α=6 frontier?

We measure the (graph-isomorphism-aware) edge-edit distance:

    d(G7, G6) = min over permutations π of |E(G7) Δ E(π · G6)|

This lower-bounds the number of edge toggles needed to transform one
graph into the other. Combined with how each move reshapes edges:

    move        |ΔE| (edges added or removed)
    -----       -----
    2-switch    4   (2 removed + 2 added)
    flip        1
    3-switch    6

→ minimum 2-switch hops ≥ d/4, minimum 3-switch hops ≥ d/6. If d is
small (say ≤ 8), the wall is *navigation*, not move-set sufficiency.
If d is large (≥ 20), no local move set bridges in any reasonable
number of iterations.

Computing the optimal π is GAP-hard in general, but for N=23 we get a
useful upper bound by:
  1. Aligning vertices by degree sort (tie-break by sum of neighbour
     degrees).
  2. Running 200 random-restart 2-opt swaps on the alignment to
     reduce |E(G7) Δ E(π·G6)|.

The reported number is the min across (a) original labelling,
(b) sorted alignment, (c) 200 random + 200 hill-climb iterations.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db.db import DB
from search.stochastic_walk.switch_tabu import (
    SwitchTabuMixedLookaheadSearch,
    _random_nearreg_k4free,
    switch_tabu_chain_mixed,
)


def _adj_from_graph_id(db: "DB", graph_id: str) -> np.ndarray:
    G = db.nx(graph_id)
    return np.array(nx.to_numpy_array(G, dtype=np.uint8))


def _sat_alpha6_adj(n: int = 23) -> np.ndarray:
    """Top-1 c_log graph at N — currently α=6 c_log=0.7527."""
    with DB() as db:
        rows = [r for r in db.query(n=n) if r["c_log"] is not None]
        rows.sort(key=lambda r: r["c_log"])
        if not rows:
            raise RuntimeError("no frontier row at N=23")
        return _adj_from_graph_id(db, rows[0]["graph_id"])


def _edge_distance(adj1: np.ndarray, adj2: np.ndarray) -> int:
    """Symmetric difference of edge sets at fixed vertex labelling."""
    return int(np.triu(adj1 ^ adj2, 1).sum())


def _degree_aligned_perm(target: np.ndarray, source: np.ndarray) -> np.ndarray:
    """
    Permute `source`'s vertices so that, vertex-by-vertex, sorted-by-
    (deg, neighbour-deg-sum) ordering matches `target`'s. Returns a
    permutation array π such that source[π][:, π] is the permuted adj.
    """
    def key_vector(adj: np.ndarray) -> list[tuple[int, int]]:
        deg = adj.sum(axis=1).astype(int)
        nbr_deg_sum = (adj @ deg).astype(int)
        return [(int(deg[v]), int(nbr_deg_sum[v])) for v in range(adj.shape[0])]

    t_keys = key_vector(target)
    s_keys = key_vector(source)
    t_order = sorted(range(len(t_keys)), key=lambda v: t_keys[v])
    s_order = sorted(range(len(s_keys)), key=lambda v: s_keys[v])
    # π[t_order[i]] = s_order[i]: target's i-th sorted vertex matches source's
    perm = np.empty(len(t_keys), dtype=int)
    for i, t_v in enumerate(t_order):
        perm[t_v] = s_order[i]
    return perm


def _apply_perm(adj: np.ndarray, perm: np.ndarray) -> np.ndarray:
    return adj[perm][:, perm]


def _hillclimb_perm(
    target: np.ndarray,
    source: np.ndarray,
    perm: np.ndarray,
    *,
    n_swaps: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """
    2-opt hill climb: at each step, propose swapping two coordinates of
    `perm`, accept if the edge distance strictly decreases. Returns
    (best_perm, best_distance).
    """
    n = source.shape[0]
    cur_perm = perm.copy()
    cur = _apply_perm(source, cur_perm)
    cur_d = _edge_distance(target, cur)
    for _ in range(n_swaps):
        i = int(rng.integers(0, n))
        j = int(rng.integers(0, n))
        if i == j:
            continue
        new_perm = cur_perm.copy()
        new_perm[i], new_perm[j] = new_perm[j], new_perm[i]
        new = _apply_perm(source, new_perm)
        new_d = _edge_distance(target, new)
        if new_d < cur_d:
            cur_perm = new_perm
            cur = new
            cur_d = new_d
    return cur_perm, cur_d


def _best_distance(
    g_target: np.ndarray,
    g_source: np.ndarray,
    *,
    n_random_perms: int,
    n_hillclimb_steps: int,
    rng: np.random.Generator,
) -> dict:
    """
    Best lower-bound proxy for isomorphism-distance:
      raw   — original labelling
      deg   — degree-sorted alignment
      hc    — degree-sorted alignment + hill-climb
      rand_hc — best of n_random_perms random restarts each hill-climbed
    """
    n = g_target.shape[0]
    raw = _edge_distance(g_target, g_source)

    deg_perm = _degree_aligned_perm(g_target, g_source)
    deg_d = _edge_distance(g_target, _apply_perm(g_source, deg_perm))

    _, hc_d = _hillclimb_perm(
        g_target, g_source, deg_perm,
        n_swaps=n_hillclimb_steps, rng=rng,
    )

    rand_best_d = hc_d
    rand_best_perm = deg_perm
    for _ in range(n_random_perms):
        perm = rng.permutation(n)
        _, d = _hillclimb_perm(
            g_target, g_source, perm,
            n_swaps=n_hillclimb_steps, rng=rng,
        )
        if d < rand_best_d:
            rand_best_d = d

    return {
        "raw_labelling": raw,
        "deg_aligned": deg_d,
        "deg_aligned_hc": hc_d,
        "rand_restart_hc": rand_best_d,
    }


def _produce_chain_best_alpha7(n: int, *, seed: int, n_iters: int) -> np.ndarray:
    """Run the mixed+swap3 chain and return its best α=7 (or whatever) adj."""
    rng = np.random.default_rng(seed)
    init = _random_nearreg_k4free(n, 4, rng)
    res = switch_tabu_chain_mixed(
        init,
        n_iters=n_iters,
        sample_size_swap=80,
        sample_size_flip=40,
        sample_size_swap3=80,
        top_k=6,
        lb_restarts=12,
        tabu_len=18,
        patience=100,
        perturb_swaps=5,
        spread_cap=1,
        rng=rng,
        time_limit_s=240.0,
    )
    return res.best_adj, res.best_alpha, res.best_c_log


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n_iters", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n_random_perms", type=int, default=200)
    p.add_argument("--n_hillclimb_steps", type=int, default=2000)
    p.add_argument("--use_existing_alpha7", action="store_true",
                   help="Pull a c_log=0.8782 α=7 graph from graph_db instead "
                        "of running the chain (faster, deterministic).")
    args = p.parse_args()

    n = 23
    rng = np.random.default_rng(args.seed)

    sat6 = _sat_alpha6_adj(n)
    sat6_m = int(sat6.sum() // 2)
    sat6_degs = sorted(sat6.sum(axis=1).astype(int).tolist(), reverse=True)
    print(f"SAT α=6 frontier: m={sat6_m}, degs={sat6_degs}")

    if args.use_existing_alpha7:
        with DB() as db:
            rows = [r for r in db.query(n=n)
                    if r["c_log"] is not None and r["alpha"] == 7]
            rows.sort(key=lambda r: r["c_log"])
            if not rows:
                raise RuntimeError("no α=7 graph at N=23 in graph_db")
            r0 = rows[0]
            chain7 = _adj_from_graph_id(db, r0["graph_id"])
            chain_alpha = r0["alpha"]
            chain_c = r0["c_log"]
            chain_src = r0["source"]
        print(f"Using existing α=7: source={chain_src}, c_log={chain_c:.4f}")
    else:
        t0 = time.monotonic()
        chain7, chain_alpha, chain_c = _produce_chain_best_alpha7(
            n, seed=args.seed, n_iters=args.n_iters,
        )
        elapsed = time.monotonic() - t0
        print(f"Chain best (seed={args.seed}, {args.n_iters} iters): "
              f"α={chain_alpha}, c_log={chain_c:.4f}, wall={elapsed:.1f}s")

    chain7_m = int(chain7.sum() // 2)
    chain7_degs = sorted(chain7.sum(axis=1).astype(int).tolist(), reverse=True)
    print(f"Chain best:           m={chain7_m}, degs={chain7_degs}")

    if chain_alpha != 7:
        print(f"\n[WARN] chain best is α={chain_alpha}, not 7. Distance "
              f"reported below is to whatever the chain reached.")

    print(f"\nEdge edit distance |E(chain) Δ E(SAT α=6)| (lower-bound proxies):")
    out = _best_distance(
        sat6, chain7,
        n_random_perms=args.n_random_perms,
        n_hillclimb_steps=args.n_hillclimb_steps,
        rng=rng,
    )
    for k, v in out.items():
        # Each 2-switch toggles 4 edges (2 add + 2 remove). 3-switch: 6.
        # |Δ| = number of edge toggles needed.
        print(f"  {k:>20}: |Δ| = {v}  → ≥ {v // 4} 2-switches, ≥ {v // 6} 3-switches")

    best_d = min(out.values())
    print(f"\nTightest upper bound on isomorphism-distance: |Δ| = {best_d}")
    print(f"  → α=7 → α=6 needs at least ≈ {best_d // 4} 2-switch moves "
          f"or ≈ {best_d // 6} 3-switch moves.")


if __name__ == "__main__":
    main()
