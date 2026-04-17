#!/usr/bin/env python3
"""
Pair-Forced Cross-Edge Experiment on Paley P(17)
================================================

Phase 1: For 2 disjoint copies of P(17) (N=34, α=6), test every cross-edge
         (289 of them) and record which drop α from 6 to 5.

Phase 2: Greedy multi-edge wiring — add cross-edges one at a time, always
         picking the one that drops α the most (SAT scored).

Phase 3: k-copy scaling (k=3..6) — only if pair-forced density > 50%.

Note: Prior work (forced_matching/ extension) established that P(17) has
zero α-forced vertices, so single-cross-edge drops are predicted to be 0/289.
Phase 2/3 test whether *combinations* of edges can still drop α.

Output: experiments/pair_forced/{pair_density.json, greedy_trajectory_k*.json,
c_vs_k.png, summary.md}

Usage:
    micromamba run -n funsearch python experiments/pair_forced/run_experiment.py
"""

import argparse
import importlib.util
import itertools
import json
import math
import os
import random
import sys
import time
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.stdout.reconfigure(line_buffering=True)

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_bd = _load_module(
    "block_decomp",
    os.path.join(_HERE, "..", "block_decomposition", "run_experiment.py"),
)
alpha_exact = _bd.alpha_exact
alpha_sat = _bd.alpha_sat
is_k4_free = _bd.is_k4_free
compute_c_value = _bd.compute_c_value

OUTDIR = _HERE


# =============================================================================
# Paley P(17)
# =============================================================================

def paley_graph_17():
    n = 17
    qr = {pow(x, 2, 17) for x in range(1, 17)}  # {1,2,4,8,9,13,15,16}
    adj = np.zeros((n, n), dtype=np.bool_)
    for u in range(n):
        for v in range(n):
            if u != v and ((u - v) % 17) in qr:
                adj[u, v] = True
    return adj


def verify_paley():
    adj = paley_graph_17()
    assert np.array_equal(adj, adj.T), "Paley not symmetric"
    degs = adj.sum(axis=1)
    assert (degs == 8).all(), f"Paley not 8-regular: {degs.tolist()}"
    assert is_k4_free(adj), "Paley not K4-free"
    a, _ = alpha_exact(adj)
    assert a == 3, f"Paley α should be 3, got {a}"
    n_edges = int(adj.sum()) // 2
    assert n_edges == 68, f"Paley should have 68 edges, got {n_edges}"
    print(f"  Paley P(17) verified: 17 vertices, 8-regular, K4-free, α=3, 68 edges")
    return adj


# =============================================================================
# Shared utilities
# =============================================================================

def compute_nbr_masks(adj):
    n = adj.shape[0]
    nbr = [0] * n
    for i in range(n):
        m = 0
        for j in range(n):
            if adj[i, j]:
                m |= 1 << j
        nbr[i] = m
    return nbr


def would_create_k4(nbr, u, v):
    common = nbr[u] & nbr[v]
    tmp = common
    while tmp:
        c = (tmp & -tmp).bit_length() - 1
        if nbr[c] & (common & ~(1 << c)):
            return True
        tmp &= tmp - 1
    return False


def greedy_mis(adj):
    """Greedy max IS; lower bound on α."""
    n = adj.shape[0]
    if n == 0:
        return 0
    remaining = set(range(n))
    size = 0
    while remaining:
        best = min(remaining, key=lambda v: sum(1 for u in remaining if adj[v, u]))
        size += 1
        remaining.discard(best)
        for u in list(remaining):
            if adj[best, u]:
                remaining.discard(u)
    return size


def sat_alpha(adj, timeout=60):
    n = adj.shape[0]
    if n == 0:
        return 0, False
    if n <= 16:
        a, _ = alpha_exact(adj)
        return int(a), False
    a, _, to = alpha_sat(adj, timeout=timeout)
    return int(a), bool(to)


def build_disjoint_copies(paley_adj, k):
    """Return (adj, offsets) for k disjoint copies of paley_adj."""
    n = paley_adj.shape[0]
    N = n * k
    adj = np.zeros((N, N), dtype=np.bool_)
    offsets = [i * n for i in range(k)]
    for o in offsets:
        adj[o:o+n, o:o+n] = paley_adj
    return adj, offsets


# =============================================================================
# Phase 1: pair-forced density
# =============================================================================

def phase1_pair_density(paley_adj, sat_timeout=30):
    """For 2 copies of P(17), test every cross-edge and record α."""
    n = paley_adj.shape[0]
    print(f"\n[Phase 1] Pair-forced density on 2 copies of P(17)")
    adj_base, offsets = build_disjoint_copies(paley_adj, 2)
    alpha_base, _ = sat_alpha(adj_base, timeout=sat_timeout)
    print(f"  Base α (disjoint union) = {alpha_base}  (expected 6)")
    assert alpha_base == 6, "disjoint α should be 6"

    records = []
    t0 = time.time()
    total = n * n
    for u1 in range(n):
        for u2 in range(n):
            gu = offsets[0] + u1
            gv = offsets[1] + u2
            adj = adj_base.copy()
            adj[gu, gv] = adj[gv, gu] = True
            a_new, to = sat_alpha(adj, timeout=sat_timeout)
            dropped = (a_new == alpha_base - 1)
            d_max = int(adj.sum(axis=1).max())
            c = compute_c_value(a_new, n * 2, d_max) if d_max >= 2 else None
            records.append({
                "u1": u1,
                "u2": u2,
                "alpha_after": int(a_new),
                "alpha_dropped": bool(dropped),
                "d_max": d_max,
                "c": round(c, 4) if c is not None and math.isfinite(c) else None,
                "timed_out": bool(to),
            })
            done = len(records)
            if done % 50 == 0 or done == total:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (total - done) / rate if rate > 0 else 0
                print(f"  [{done}/{total}] elapsed {elapsed:.1f}s, ETA {eta:.1f}s")

    density = sum(1 for r in records if r["alpha_dropped"])
    print(f"  Pair-forced density: {density}/{total} = {density/total:.4f}")
    # Check uniformity via (u1=0) rows
    u0_results = [r for r in records if r["u1"] == 0]
    u0_alphas = [r["alpha_after"] for r in u0_results]
    print(f"  u1=0 row α values: {sorted(set(u0_alphas))} "
          f"(uniform: {len(set(u0_alphas)) == 1})")

    out = {
        "alpha_base": int(alpha_base),
        "N": n * 2,
        "num_candidate_edges": total,
        "num_alpha_dropping": density,
        "pair_forced_density": round(density / total, 4),
        "u0_row_uniform": (len(set(u0_alphas)) == 1),
        "u0_row_alphas": [r["alpha_after"] for r in u0_results],
        "records": records,
    }
    return out


# =============================================================================
# Phase 2 / 3: greedy multi-edge wiring
# =============================================================================

def enumerate_cross_edges(adj, offsets, nbr, degs, d_cap, block_size):
    """All valid cross-edges: between different copies, K4-free safe, d<d_cap."""
    N = adj.shape[0]
    cands = []
    num_copies = len(offsets)
    for bi in range(num_copies):
        for bj in range(bi + 1, num_copies):
            for u in range(offsets[bi], offsets[bi] + block_size):
                if degs[u] >= d_cap:
                    continue
                for v in range(offsets[bj], offsets[bj] + block_size):
                    if degs[v] >= d_cap:
                        continue
                    if adj[u, v]:
                        continue
                    if would_create_k4(nbr, u, v):
                        continue
                    cands.append((u, v))
    return cands


def greedy_cross_edge_trajectory(paley_adj, k_copies, d_cap=12,
                                 sat_timeout=30, top_k_candidates=5,
                                 max_steps=500):
    """Greedily add cross-edges between k copies of Paley.
    At each step, pre-filter candidates by greedy MIS, score top-k with SAT,
    add the edge that drops α most. Stop at d_max=d_cap or no further drop."""
    n = paley_adj.shape[0]
    N = n * k_copies
    adj, offsets = build_disjoint_copies(paley_adj, k_copies)
    nbr = compute_nbr_masks(adj)
    degs = [int(adj[i].sum()) for i in range(N)]

    alpha_current, _ = sat_alpha(adj, timeout=sat_timeout)
    d_max_initial = int(max(degs))
    trajectory = [{
        "step": 0,
        "edge_added": None,
        "edges_so_far": 0,
        "alpha": int(alpha_current),
        "d_max": d_max_initial,
        "c": round(compute_c_value(alpha_current, N, d_max_initial), 4)
             if d_max_initial >= 2 else None,
    }]
    print(f"  k={k_copies} N={N} initial α={alpha_current} d_max={d_max_initial}")

    step = 0
    no_drop_streak = 0
    while step < max_steps:
        cands = enumerate_cross_edges(adj, offsets, nbr, degs, d_cap, n)
        if not cands:
            print(f"  step {step}: no valid candidates left")
            break

        # Pre-filter: greedy MIS per candidate (fast)
        scored = []
        for u, v in cands:
            adj[u, v] = adj[v, u] = True
            nbr[u] |= 1 << v; nbr[v] |= 1 << u
            gmis = greedy_mis(adj)
            adj[u, v] = adj[v, u] = False
            nbr[u] &= ~(1 << v); nbr[v] &= ~(1 << u)
            scored.append((gmis, (u, v)))
        scored.sort()  # smallest gmis first (suggests lower α)
        top = scored[:top_k_candidates]

        # SAT-score the top candidates
        best_uv = None
        best_alpha = alpha_current  # must strictly improve
        best_d_max = None
        for _, (u, v) in top:
            adj[u, v] = adj[v, u] = True
            nbr[u] |= 1 << v; nbr[v] |= 1 << u
            degs[u] += 1; degs[v] += 1
            a, _ = sat_alpha(adj, timeout=sat_timeout)
            adj[u, v] = adj[v, u] = False
            nbr[u] &= ~(1 << v); nbr[v] &= ~(1 << u)
            degs[u] -= 1; degs[v] -= 1
            if a < best_alpha or (a == best_alpha and best_uv is None):
                best_alpha = a
                best_uv = (u, v)

        if best_uv is None:
            print(f"  step {step}: no candidate dropped α")
            break

        # If SAT-best didn't strictly drop α, we allow the first top-k edge
        # (so the graph grows), but we count as no-drop for streak
        u, v = best_uv
        adj[u, v] = adj[v, u] = True
        nbr[u] |= 1 << v; nbr[v] |= 1 << u
        degs[u] += 1; degs[v] += 1
        if best_alpha < alpha_current:
            no_drop_streak = 0
        else:
            no_drop_streak += 1
            if no_drop_streak >= 10:
                # reverse last edge
                adj[u, v] = adj[v, u] = False
                nbr[u] &= ~(1 << v); nbr[v] &= ~(1 << u)
                degs[u] -= 1; degs[v] -= 1
                print(f"  step {step}: α plateau for {no_drop_streak} steps — stopping")
                break
        alpha_current = best_alpha
        d_max_new = int(max(degs))
        step += 1
        c_val = compute_c_value(alpha_current, N, d_max_new) if d_max_new >= 2 else None
        trajectory.append({
            "step": step,
            "edge_added": [int(u), int(v)],
            "edges_so_far": step,
            "alpha": int(alpha_current),
            "d_max": d_max_new,
            "c": round(c_val, 4) if c_val is not None and math.isfinite(c_val) else None,
        })
        if step % 5 == 0 or step < 5:
            print(f"    step {step}: added ({u},{v}), α={alpha_current}, "
                  f"d_max={d_max_new}, c={trajectory[-1]['c']}")
        if d_max_new >= d_cap:
            # still allow completing this step; stop next
            print(f"  d_max reached cap {d_cap} — stopping")
            break

    # Report best
    best = min((t for t in trajectory if t["c"] is not None),
               key=lambda t: t["c"], default=None)
    return {
        "k_copies": k_copies,
        "N": N,
        "d_cap": d_cap,
        "trajectory": trajectory,
        "final_alpha": int(alpha_current),
        "final_d_max": int(max(degs)),
        "num_edges_added": step,
        "best_step": best,
    }


# =============================================================================
# Plots + Summary
# =============================================================================

def plot_c_vs_k(k_results, out_path, floor=0.9017, sat_opt=None):
    fig, ax = plt.subplots(figsize=(10, 6))
    ks = sorted(k_results)
    best_cs = [k_results[k]["best_step"]["c"] if k_results[k].get("best_step") else None for k in ks]
    Ns = [k_results[k]["N"] for k in ks]
    xs = [k for k, c in zip(ks, best_cs) if c is not None]
    ys = [c for c in best_cs if c is not None]
    ax.plot(xs, ys, "-o", color="C0", markersize=9, linewidth=2,
            label="P(17) pair-forced greedy")
    for k, N, c in zip(ks, Ns, best_cs):
        if c is not None:
            ax.annotate(f"N={N}\nc={c:.3f}", (k, c), fontsize=8,
                        xytext=(8, 8), textcoords="offset points")

    ax.axhline(floor, linestyle="-.", color="purple", alpha=0.6,
               label=f"forced_matching floor = {floor:.4f}")
    ax.axhline(0.72, linestyle="--", color="red", alpha=0.7,
               label="SAT-optimal ~0.72 (N=16)")
    ax.axhline(1.15, linestyle=":", color="gray", label="random ~1.15")

    ax.set_xlabel("k (number of P(17) copies)")
    ax.set_ylabel(r"best $c = \alpha \cdot d_{\max} / (N \log d_{\max})$")
    ax.set_title("c vs k for greedy cross-edge wiring between P(17) copies")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def write_summary(phase1, k_results, out_path, runtime_s):
    lines = [
        "# Pair-Forced Cross-Edge Experiment on Paley P(17)",
        "",
        f"- Runtime: **{runtime_s/60:.1f} min**",
        "- Base: 2 disjoint copies of P(17), N=34, α=6",
        "",
        "## Phase 1 — Pair-forced density",
        "",
        f"- Candidate cross-edges tested: {phase1['num_candidate_edges']} (17×17)",
        f"- Edges that dropped α (6 → 5): **{phase1['num_alpha_dropping']}**",
        f"- **Pair-forced density = {phase1['pair_forced_density']:.4f}**",
        f"- u₁=0 row uniform across all 17 targets: {phase1['u0_row_uniform']}",
        f"- u₁=0 row α-after values: {phase1['u0_row_alphas']}",
        "",
    ]
    if phase1["num_alpha_dropping"] == 0:
        lines += [
            "**Finding — no single cross-edge drops α.**",
            "",
            "This is consistent with the prior result that P(17) has no α-forced",
            "vertex: α(P(17) − v) = 3 for every v. Adding one edge (u₁, u₂) can",
            "only drop α if every max-IS of the disjoint union uses **both** u₁",
            "and u₂ — but because no vertex is forced in either copy, a max-IS",
            "avoiding u₁ (resp. u₂) always exists, so α stays at 6.",
            "",
            "Phase 3 (k-copy scaling) was skipped per the '>50% density' gate.",
            "However, Phase 2 still tested whether combinations of edges can",
            "jointly drop α — see below.",
            "",
        ]
    elif phase1["pair_forced_density"] > 0.5:
        lines += [
            "**Finding — high pair-forced density.** Many single cross-edges",
            "drop α; Phase 3 scaling was run.",
            "",
        ]
    else:
        lines += [
            f"**Finding — partial pair-forced density ({phase1['pair_forced_density']:.4f}).**",
            "",
        ]

    # Phase 2 / 3 results
    if k_results:
        lines += [
            "## Phase 2/3 — Greedy multi-edge trajectories",
            "",
            "| k | N | d_cap | #edges added | final α | final d_max | best c | best step | Δc vs floor |",
            "|---|---|-------|--------------|---------|-------------|--------|-----------|-------------|",
        ]
        for k in sorted(k_results):
            res = k_results[k]
            best = res.get("best_step")
            if best and best["c"] is not None:
                delta = best["c"] - 0.9017
                lines.append(
                    f"| {k} | {res['N']} | {res['d_cap']} | {res['num_edges_added']} | "
                    f"{res['final_alpha']} | {res['final_d_max']} | "
                    f"{best['c']:.4f} | {best['step']} | {delta:+.4f} |"
                )
            else:
                lines.append(
                    f"| {k} | {res['N']} | {res['d_cap']} | {res['num_edges_added']} | "
                    f"{res['final_alpha']} | {res['final_d_max']} | — | — | — |"
                )
        lines.append("")

        # Did any k beat the floor?
        beat = [k for k, r in k_results.items()
                if r.get("best_step") and r["best_step"]["c"] is not None
                and r["best_step"]["c"] < 0.9017]
        lines += [
            "## Did greedy cross-edge wiring break the 0.9017 floor?",
            "",
        ]
        if beat:
            best_k = min(beat, key=lambda k: k_results[k]["best_step"]["c"])
            best_c = k_results[best_k]["best_step"]["c"]
            lines += [
                f"**Yes.** Best c = {best_c:.4f} at k={best_k} "
                f"(N={k_results[best_k]['N']}).",
                "",
            ]
        else:
            lines += [
                "**No.** Greedy cross-edge wiring on Paley copies did not beat",
                f"the forced_matching floor of 0.9017.",
                "",
                "Best results per k above.",
                "",
            ]

    lines += [
        "## Files",
        "",
        "- `pair_density.json` — full 289-edge records",
        "- `greedy_trajectory_k{2,3,...}.json` — step-by-step trajectories",
        "- `c_vs_k.png` — best c vs k plot",
    ]

    with open(out_path, "w") as f:
        f.write("\n".join(lines))


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase1-only", action="store_true")
    parser.add_argument("--skip-phase1", action="store_true")
    parser.add_argument("--sat-timeout", type=int, default=30)
    parser.add_argument("--d-cap", type=int, default=12)
    parser.add_argument("--k-max", type=int, default=6)
    parser.add_argument("--top-k-candidates", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=200)
    args = parser.parse_args()

    os.makedirs(OUTDIR, exist_ok=True)
    t0 = time.time()

    print("=" * 60)
    print("Pair-Forced Cross-Edge Experiment — Paley P(17)")
    print("=" * 60)
    paley = verify_paley()

    # --- Phase 1 ---
    phase1 = None
    if not args.skip_phase1:
        phase1 = phase1_pair_density(paley, sat_timeout=args.sat_timeout)
        with open(os.path.join(OUTDIR, "pair_density.json"), "w") as f:
            json.dump(phase1, f, indent=2)
        print(f"  Wrote pair_density.json")

    if args.phase1_only:
        print("\n[Phase 1 only — skipping Phase 2/3]")
        if phase1:
            write_summary(phase1, {}, os.path.join(OUTDIR, "summary.md"),
                          time.time() - t0)
        return

    # --- Phase 2: k=2 always runs ---
    print(f"\n[Phase 2] Greedy cross-edge trajectory on 2 copies (d_cap={args.d_cap})")
    k_results = {}
    traj_k2 = greedy_cross_edge_trajectory(
        paley, 2, d_cap=args.d_cap,
        sat_timeout=args.sat_timeout,
        top_k_candidates=args.top_k_candidates,
        max_steps=args.max_steps,
    )
    k_results[2] = traj_k2
    with open(os.path.join(OUTDIR, "greedy_trajectory_k2.json"), "w") as f:
        json.dump(traj_k2, f, indent=2)

    # --- Phase 3: only if pair density > 50%, or k_max explicitly set ---
    run_phase3 = True
    if phase1 is not None:
        if phase1["pair_forced_density"] <= 0.5:
            print(f"\n[Phase 3] SKIPPED — pair density {phase1['pair_forced_density']:.4f} ≤ 0.5")
            run_phase3 = False

    if run_phase3 and args.k_max >= 3:
        for k in range(3, args.k_max + 1):
            # SAT timeout grows with N
            to = max(args.sat_timeout, 10 + k * 5)
            try:
                traj = greedy_cross_edge_trajectory(
                    paley, k, d_cap=args.d_cap,
                    sat_timeout=to,
                    top_k_candidates=args.top_k_candidates,
                    max_steps=args.max_steps,
                )
                k_results[k] = traj
                path = os.path.join(OUTDIR, f"greedy_trajectory_k{k}.json")
                with open(path, "w") as f:
                    json.dump(traj, f, indent=2)
            except Exception as e:
                print(f"  k={k} FAILED: {e}")

    # --- Plots + Summary ---
    plot_c_vs_k(k_results, os.path.join(OUTDIR, "c_vs_k.png"))
    print("\nWrote c_vs_k.png")

    if phase1 is not None:
        write_summary(phase1, k_results, os.path.join(OUTDIR, "summary.md"),
                      time.time() - t0)
        print("Wrote summary.md")

    print(f"\nDone in {(time.time()-t0)/60:.1f} min.")


if __name__ == "__main__":
    main()
