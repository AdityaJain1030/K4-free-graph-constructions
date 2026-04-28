"""
scripts/diag_n23_path_to_alpha6.py
====================================
Construct an explicit, K4-free legal sequence of edge moves from the
chain's best α=7 graph to (an isomorphic copy of) the SAT α=6 frontier,
and print the c_log / α / d_max / m trajectory at every step.

Why: the edit-distance check showed the two graphs are ~16-23 edges
apart under best vertex alignment — only 4-5 2-switches' worth. The
switch_tabu chain runs hundreds of accepted moves but never finds the
bridge. The hypothesis: every step toward the bridge worsens the
composite (exact α, α_lb, c_log) score, so the greedy ranker
categorically refuses to walk uphill.

This script tests that hypothesis directly. It builds one concrete path
and shows how the score evolves. If the *maximum* c_log along the path
is high (and the greedy ranker would never tolerate it), perfect-
information lookahead doesn't bail out the c_log greedy — only an
actual uphill-tolerating acceptance rule (annealing / MCMC at
moderate β / Bellman-style multi-step value estimates) does.

Construction
------------
1. Compute G7 by running the mixed+swap3 chain.
2. Pick the best vertex alignment π* of G6 onto G7 by edit-distance
   hill climb.
3. Form the symmetric difference Δ = E(G7) Δ E(π*·G6) and split into
   chain_only (must remove) and sat_only (must add).
4. Two phase plan:
     phase 1 — remove every chain_only edge (each removal is K4-safe by
               construction).
     phase 2 — add every sat_only edge in an order that keeps the graph
               K4-free at every step. We try the natural order, falling
               back to local reordering if a step would create K4.
5. At every step, compute (m, d_max, α, c_log) and print one row.

If for some seed the chain reaches a different multiset and the path
construction stalls, run with `--seed N` to retry. The script logs
the first failing addition, which usually points to a K4 wall the
naive ordering hits — the user can then inspect.
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

from graph_db.db import DB
from utils.graph_props import alpha_bb_clique_cover, find_k4, c_log_value
from search.stochastic_walk.switch_tabu import (
    _random_nearreg_k4free,
    switch_tabu_chain_mixed,
)
from scripts.diag_n23_edit_distance import (
    _hillclimb_perm,
    _degree_aligned_perm,
    _apply_perm,
    _edge_distance,
    _sat_alpha6_adj,
)


def _state_metrics(adj: np.ndarray) -> dict:
    n = adj.shape[0]
    deg = adj.sum(axis=1).astype(int)
    d_max = int(deg.max())
    m = int(adj.sum() // 2)
    a, _ = alpha_bb_clique_cover(adj)
    cl = c_log_value(a, n, d_max)
    return {
        "m": m,
        "d_max": d_max,
        "alpha": a,
        "c_log": cl if cl is not None else float("inf"),
    }


def _best_alignment(
    target: np.ndarray,
    source: np.ndarray,
    *,
    n_random_perms: int,
    n_hillclimb_steps: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, int]:
    """Return (best_perm, best_distance) — the alignment minimising |E(target) Δ E(perm·source)|."""
    n = target.shape[0]
    best_perm = _degree_aligned_perm(target, source)
    best_perm, best_d = _hillclimb_perm(
        target, source, best_perm,
        n_swaps=n_hillclimb_steps, rng=rng,
    )
    for _ in range(n_random_perms):
        perm = rng.permutation(n)
        perm, d = _hillclimb_perm(
            target, source, perm,
            n_swaps=n_hillclimb_steps, rng=rng,
        )
        if d < best_d:
            best_d = d
            best_perm = perm
    return best_perm, best_d


def _diff_edges(
    g_from: np.ndarray, g_to: np.ndarray,
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """
    Return (chain_only, sat_only) edge lists at fixed vertex labelling.
    chain_only: edges in g_from but not in g_to (must be removed).
    sat_only:   edges in g_to but not in g_from (must be added).
    """
    n = g_from.shape[0]
    chain_only, sat_only = [], []
    for i in range(n):
        for j in range(i + 1, n):
            if g_from[i, j] and not g_to[i, j]:
                chain_only.append((i, j))
            elif g_to[i, j] and not g_from[i, j]:
                sat_only.append((i, j))
    return chain_only, sat_only


def _try_add(adj: np.ndarray, u: int, v: int) -> np.ndarray | None:
    new = adj.copy()
    new[u, v] = new[v, u] = 1
    if find_k4(new) is not None:
        return None
    return new


def _plan_addition_order(
    adj: np.ndarray, sat_only: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], int]:
    """
    Greedy-with-backtracking ordering of additions that keeps every
    intermediate K4-free.

    Strategy: at each step, pick *any* still-needed edge whose addition
    would not create K4 in the current graph. If none exists, we're
    stuck (return what we have so far + count of remaining).

    Empirically: at the post-removal sparsity (m≈33), the K4 walls are
    far enough that the natural order works.
    """
    cur = adj.copy()
    plan: list[tuple[int, int]] = []
    remaining = list(sat_only)

    while remaining:
        progressed = False
        for idx, (u, v) in enumerate(remaining):
            new = _try_add(cur, u, v)
            if new is not None:
                cur = new
                plan.append((u, v))
                remaining.pop(idx)
                progressed = True
                break
        if not progressed:
            break
    return plan, len(remaining)


def _produce_chain_g7(seed: int, n_iters: int) -> tuple[np.ndarray, dict]:
    rng = np.random.default_rng(seed)
    init = _random_nearreg_k4free(23, 4, rng)
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
    return res.best_adj, {
        "best_alpha": res.best_alpha,
        "best_c_log": float(res.best_c_log),
        "n_iters": res.n_iters,
        "n_accepted": res.n_accepted,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--n_iters", type=int, default=2000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n_random_perms", type=int, default=400)
    p.add_argument("--n_hillclimb_steps", type=int, default=4000)
    args = p.parse_args()

    n = 23
    rng = np.random.default_rng(args.seed)

    print("=== Stage 1: produce chain's best α=7 graph ===")
    t0 = time.monotonic()
    g7, chain_meta = _produce_chain_g7(args.seed, args.n_iters)
    print(f"  chain best: α={chain_meta['best_alpha']}, "
          f"c_log={chain_meta['best_c_log']:.4f}, "
          f"n_accepted={chain_meta['n_accepted']}, "
          f"wall={time.monotonic() - t0:.1f}s")

    g6 = _sat_alpha6_adj(n)

    print("\n=== Stage 2: find best vertex alignment ===")
    t0 = time.monotonic()
    best_perm, best_d = _best_alignment(
        g7, g6,
        n_random_perms=args.n_random_perms,
        n_hillclimb_steps=args.n_hillclimb_steps,
        rng=rng,
    )
    g6_aligned = _apply_perm(g6, best_perm)
    print(f"  |Δ| (best aligned) = {best_d}, wall={time.monotonic() - t0:.1f}s")

    chain_only, sat_only = _diff_edges(g7, g6_aligned)
    print(f"  edges to remove (chain only): {len(chain_only)}")
    print(f"  edges to add    (sat   only): {len(sat_only)}")

    print("\n=== Stage 3: trajectory — phase 1 (removals), phase 2 (additions) ===")
    rows = []
    cur = g7.copy()
    rows.append({"step": 0, "phase": "start", "move": "G7", **_state_metrics(cur)})

    # Interleaved order: alternate remove and add so m oscillates near
    # the start value rather than dipping to 33. The K4 risk on adds is
    # higher because intermediates are denser, so we plan greedily.
    rem_q = list(chain_only)
    add_q = list(sat_only)
    step = 0
    while rem_q or add_q:
        # Try an add first (denser → harder); fall back to a remove.
        added = False
        for idx in range(len(add_q)):
            u, v = add_q[idx]
            new = _try_add(cur, u, v)
            if new is not None:
                cur = new
                add_q.pop(idx)
                step += 1
                rows.append({
                    "step": step, "phase": "add",
                    "move": f"+({u},{v})",
                    **_state_metrics(cur),
                })
                added = True
                break
        if added:
            # Now try a remove to keep m near the start.
            if rem_q:
                u, v = rem_q.pop(0)
                cur[u, v] = cur[v, u] = 0
                step += 1
                rows.append({
                    "step": step, "phase": "rm",
                    "move": f"-({u},{v})",
                    **_state_metrics(cur),
                })
            continue
        # No add was K4-safe — must remove first.
        if rem_q:
            u, v = rem_q.pop(0)
            cur[u, v] = cur[v, u] = 0
            step += 1
            rows.append({
                "step": step, "phase": "rm",
                "move": f"-({u},{v})",
                **_state_metrics(cur),
            })
        else:
            print(f"  [WARN] interleaved planner stalled with {len(add_q)} adds left")
            break

    final = _state_metrics(cur)
    target = _state_metrics(g6_aligned)
    print(f"\n  reached: m={final['m']}, d_max={final['d_max']}, "
          f"α={final['alpha']}, c_log={final['c_log']:.4f}")
    print(f"  target:  m={target['m']}, d_max={target['d_max']}, "
          f"α={target['alpha']}, c_log={target['c_log']:.4f}")
    print(f"  match (final == target): {np.array_equal(cur, g6_aligned)}")

    print("\n=== Stage 4: telescoping table ===")
    print(f"  {'step':>4} {'phase':>5} {'move':>14} {'m':>3} "
          f"{'d':>3} {'α':>3} {'c_log':>7} {'Δc_log vs G7':>13} "
          f"{'Δc_log vs G6':>13}")
    print("  " + "-" * 80)
    g7_clog = rows[0]["c_log"]
    g6_clog = target["c_log"]
    for r in rows:
        cl = r["c_log"]
        d7 = cl - g7_clog if np.isfinite(cl) else float("inf")
        d6 = cl - g6_clog if np.isfinite(cl) else float("inf")
        cl_str = f"{cl:.4f}" if np.isfinite(cl) else "inf"
        print(
            f"  {r['step']:>4} {r['phase']:>5} {r['move']:>14} {r['m']:>3} "
            f"{r['d_max']:>3} {r['alpha']:>3} {cl_str:>7} "
            f"{d7:+.4f} {d6:+.4f}".rstrip()
        )

    # Headline summary the user wants for "would future-reward help".
    finite_logs = [r["c_log"] for r in rows if np.isfinite(r["c_log"])]
    peak = max(finite_logs)
    peak_step = max(rows, key=lambda r: r["c_log"] if np.isfinite(r["c_log"]) else -1)
    print()
    print(f"=== Summary ===")
    print(f"  G7 c_log:    {g7_clog:.4f}")
    print(f"  G6 c_log:    {g6_clog:.4f}")
    print(f"  peak c_log:  {peak:.4f}  at step {peak_step['step']} "
          f"(α={peak_step['alpha']}, d_max={peak_step['d_max']}, "
          f"phase={peak_step['phase']})")
    print(f"  uphill cost (peak − G7): {peak - g7_clog:+.4f}")
    print(f"  total bridge length:     {len(rows) - 1} flips")


if __name__ == "__main__":
    main()
