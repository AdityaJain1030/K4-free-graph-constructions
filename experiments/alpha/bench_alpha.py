#!/usr/bin/env python3
"""
experiments/alpha/bench_alpha.py
=================================
Head-to-head performance benchmark for every exact α solver across all
K4-free graph classes defined in generate_graphs.py.

Solvers benchmarked
-------------------
  alpha_exact              pure-Python bitmask B&B (baseline)
  alpha_bb_clique_cover    B&B with greedy clique-cover bound (project default)
  alpha_bb_numba           Numba-jitted bitmask B&B
  alpha_cpsat              OR-Tools CP-SAT
  alpha_cpsat_vt           same, vertex_transitive=True pin
  alpha_maxsat             python-sat RC2 MaxSAT
  alpha_clique_complement  Bron–Kerbosch max clique on complement

Each solver runs in a forked subprocess for isolated peak RSS measurement
(resource.getrusage) and a hard timeout aborts hung runs.

Usage
-----
    micromamba run -n k4free python experiments/alpha/bench_alpha.py
    micromamba run -n k4free python experiments/alpha/bench_alpha.py \\
        --classes synthetic_circulant prime_circulant --timeout 30
    micromamba run -n k4free python experiments/alpha/bench_alpha.py \\
        --solvers bb_clique_cover maxsat cpsat --no-slow
"""

from __future__ import annotations

import argparse
import csv
import multiprocessing as mp
import os
import resource
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import networkx as nx

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from experiments.alpha.generate_graphs import load_all, ALL_CLASSES

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
PLOTS_DIR   = os.path.join(RESULTS_DIR, "performance_plots")

SOLVERS = [
    "exact",
    "bb_clique_cover",
    "bb_numba",
    "cpsat",
    "cpsat_vt",
    "maxsat",
    "clique_complement",
]

# Solvers that time out on large/dense graphs — skip by default with --no-slow
SLOW_SOLVERS = {"exact", "bb_numba", "clique_complement"}


# ---------------------------------------------------------------------------
# Subprocess worker
# ---------------------------------------------------------------------------

def _run_solver(solver_name: str, adj_bytes: bytes, shape: tuple,
                timeout: float, q: mp.Queue) -> None:
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


def _timed(solver: str, adj: np.ndarray, timeout: float) -> tuple[int | None, float, float]:
    ctx = mp.get_context("fork")
    q: mp.Queue = ctx.Queue()
    p = ctx.Process(target=_run_solver,
                    args=(solver, adj.tobytes(), adj.shape, timeout, q))
    p.start()
    p.join(timeout + 10.0)
    if p.is_alive():
        p.terminate(); p.join(2.0)
        if p.is_alive(): p.kill()
        return None, timeout, float("nan")
    if q.empty():
        return None, -1.0, float("nan")
    alpha, dt, rss_kb = q.get()
    return alpha, dt, rss_kb / 1024.0


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

CLASS_ORDER = list(ALL_CLASSES)

SOLVER_COLORS = {
    "bb_clique_cover":   "#1f77b4",
    "cpsat":             "#ff7f0e",
    "cpsat_vt":          "#2ca02c",
    "maxsat":            "#d62728",
    "exact":             "#9467bd",
    "bb_numba":          "#8c564b",
    "clique_complement": "#e377c2",
}


def plot_results(rows: list[dict], out_dir: str) -> None:
    import math
    os.makedirs(out_dir, exist_ok=True)

    # index by (class, solver) -> list of (n, wall_s, rss_mb, status)
    from collections import defaultdict
    by_cls_solver: dict[tuple, list] = defaultdict(list)
    for r in rows:
        by_cls_solver[(r["class"], r["solver"])].append(r)

    classes  = [c for c in CLASS_ORDER if any(r["class"] == c for r in rows)]
    solvers  = list(dict.fromkeys(r["solver"] for r in rows))  # preserve order

    # --- 1. Wall time vs n: one panel per graph class, all solvers overlaid ---
    ncols = 3
    nrows = math.ceil(len(classes) / ncols)
    fig, axes = plt.subplots(nrows, ncols, figsize=(5 * ncols, 4 * nrows))
    axes = axes.flatten()

    for i, cls in enumerate(classes):
        ax = axes[i]
        for solver in solvers:
            data = sorted(by_cls_solver[(cls, solver)], key=lambda r: r["n"])
            if not data:
                continue
            ns  = [r["n"] for r in data]
            ts  = [r["wall_s"] * 1000 if r["status"] == "ok" else None for r in data]
            col = SOLVER_COLORS.get(solver, "gray")
            # plot connected segments, skip None (timeout)
            xs, ys = [], []
            for x, y in zip(ns, ts):
                if y is not None:
                    xs.append(x); ys.append(y)
                else:
                    if xs:
                        ax.semilogy(xs, ys, "o-", color=col, markersize=3, lw=1.2,
                                    label=solver if i == 0 else "_")
                    xs, ys = [], []
                    ax.axvline(x, color=col, lw=0.5, ls=":", alpha=0.5)
            if xs:
                ax.semilogy(xs, ys, "o-", color=col, markersize=3, lw=1.2,
                            label=solver if i == 0 else "_")

        ax.set_title(cls, fontsize=9)
        ax.set_xlabel("n", fontsize=8)
        ax.set_ylabel("wall (ms)", fontsize=8)
        ax.tick_params(labelsize=7)

    # hide unused panels
    for j in range(len(classes), len(axes)):
        axes[j].set_visible(False)

    # shared legend from panel 0
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower right", fontsize=8, ncol=2)
    fig.suptitle("α solver wall time by graph class (log scale)", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "wall_time_by_class.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # --- 2. Heatmap: median wall time (ms), class × solver ---
    import numpy as np
    heat_data = np.full((len(classes), len(solvers)), np.nan)
    for i, cls in enumerate(classes):
        for j, solver in enumerate(solvers):
            ts = [r["wall_s"] * 1000 for r in by_cls_solver[(cls, solver)]
                  if r["status"] == "ok"]
            if ts:
                heat_data[i, j] = sorted(ts)[len(ts) // 2]

    fig, ax = plt.subplots(figsize=(max(8, len(solvers) * 1.5), max(4, len(classes) * 0.7)))
    log_data = np.log10(np.where(heat_data > 0, heat_data, np.nan))
    im = ax.imshow(log_data, aspect="auto", cmap="RdYlGn_r")
    ax.set_xticks(range(len(solvers))); ax.set_xticklabels(solvers, rotation=30, ha="right", fontsize=9)
    ax.set_yticks(range(len(classes))); ax.set_yticklabels(classes, fontsize=9)

    for i in range(len(classes)):
        for j in range(len(solvers)):
            val = heat_data[i, j]
            txt = f"{val:.0f}" if not np.isnan(val) else "T/O"
            ax.text(j, i, txt, ha="center", va="center", fontsize=7,
                    color="white" if (np.isnan(log_data[i, j]) or log_data[i, j] > 3) else "black")

    cbar = fig.colorbar(im, ax=ax, fraction=0.03)
    cbar.set_label("log₁₀(median wall ms)", fontsize=8)
    ax.set_title("Median wall time (ms) — class × solver  [T/O = timeout]")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "wall_time_heatmap.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # --- 3. Peak RSS per solver (bar chart, median across all runs) ---
    fig, ax = plt.subplots(figsize=(max(7, len(solvers) * 1.2), 4))
    rss_vals = []
    for solver in solvers:
        vals = [r["rss_mb"] for r in rows if r["solver"] == solver
                and r["status"] == "ok" and not np.isnan(float(r["rss_mb"]))]
        rss_vals.append(sorted(vals)[len(vals) // 2] if vals else 0)
    bars = ax.bar(solvers, rss_vals, color=[SOLVER_COLORS.get(s, "gray") for s in solvers])
    for bar, val in zip(bars, rss_vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{val:.0f} MB", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("Median peak RSS (MB)")
    ax.set_title("Peak RSS per solver (median across all graphs)")
    plt.xticks(rotation=20, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "rss_by_solver.png"), dpi=150)
    plt.close(fig)

    # --- 4. Timeout rate: stacked bar per class, coloured by solver ---
    counts_ok  = defaultdict(lambda: defaultdict(int))
    counts_to  = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if r["status"] == "ok":
            counts_ok[r["class"]][r["solver"]] += 1
        else:
            counts_to[r["class"]][r["solver"]] += 1

    # only include (class, solver) pairs that had at least one timeout
    pairs = [(c, s) for c in classes for s in solvers if counts_to[c][s] > 0]
    if pairs:
        xlabels = [f"{c}\n{s}" for c, s in pairs]
        rates   = [100 * counts_to[c][s] / (counts_ok[c][s] + counts_to[c][s])
                   for c, s in pairs]
        cols    = [SOLVER_COLORS.get(s, "gray") for _, s in pairs]
        fig, ax = plt.subplots(figsize=(max(6, len(pairs) * 0.9), 4))
        ax.bar(range(len(pairs)), rates, color=cols)
        ax.set_xticks(range(len(pairs))); ax.set_xticklabels(xlabels, fontsize=8)
        ax.set_ylabel("Timeout rate (%)")
        ax.set_ylim(0, 105)
        ax.set_title("Timeout rate by class + solver (only pairs with ≥1 timeout shown)")
        fig.tight_layout()
        fig.savefig(os.path.join(out_dir, "timeout_rate.png"), dpi=150)
        plt.close(fig)

    print(f"\n  Plots saved to {out_dir}/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classes", nargs="+", choices=list(ALL_CLASSES),
                        help="Graph classes to include (default: all)")
    parser.add_argument("--solvers", nargs="+", choices=SOLVERS, default=None,
                        help="Solvers to run (default: all)")
    parser.add_argument("--no-slow", action="store_true",
                        help=f"Skip {SLOW_SOLVERS} (time out on large graphs)")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="Per-solver wall-clock timeout in seconds (default: 60)")
    parser.add_argument("--warmup-numba", action="store_true",
                        help="Warm up Numba JIT on a tiny graph before benchmarking")
    parser.add_argument("--csv", default=os.path.join(RESULTS_DIR, "performance_results.csv"),
                        help="Output CSV path")
    parser.add_argument("--no-plots", action="store_true",
                        help="Skip plot generation")
    args = parser.parse_args()

    solvers = args.solvers or SOLVERS
    if args.no_slow:
        solvers = [s for s in solvers if s not in SLOW_SOLVERS]

    print("Loading graphs...")
    graphs = load_all(args.classes)
    print(f"  {len(graphs)} graphs loaded\n")

    if args.warmup_numba and "bb_numba" in solvers:
        print("# warming Numba JIT...", flush=True)
        adj_tiny = np.array(nx.to_numpy_array(nx.cycle_graph(5), dtype=np.uint8))
        _timed("bb_numba", adj_tiny, 30.0)

    print(f"# timeout={args.timeout}s  solvers={solvers}\n")
    hdr = f"{'class':>20}  {'label':>30}  {'n':>4}  {'solver':>18}  {'α':>5}  {'wall (s)':>10}  {'RSS (MB)':>10}"
    print(hdr)
    print("-" * len(hdr))

    results: list[dict] = []
    for g in graphs:
        G   = g["graph"]
        adj = np.array(nx.to_numpy_array(G, dtype=np.uint8))
        n   = g["n"]
        cls = g["class"]
        lbl = g["label"]
        alphas_seen: set[int] = set()

        for solver in solvers:
            alpha, dt, rss_mb = _timed(solver, adj, args.timeout)
            if alpha is None:
                status = "timeout"
                print(f"{cls:>20}  {lbl:>30}  {n:>4}  {solver:>18}  {'—':>5}  {'timeout':>10}  {rss_mb:>10.1f}")
            else:
                alphas_seen.add(alpha)
                status = "ok"
                print(f"{cls:>20}  {lbl:>30}  {n:>4}  {solver:>18}  {alpha:>5}  {dt:>10.4f}  {rss_mb:>10.1f}")

            results.append({
                "class":    cls,
                "label":    lbl,
                "n":        n,
                "solver":   solver,
                "alpha":    alpha,
                "wall_s":   round(dt, 4),
                "rss_mb":   round(rss_mb, 1),
                "status":   status,
            })

        if len(alphas_seen - {0}) > 1:
            print(f"  !! DISAGREEMENT at {cls} {lbl}: alphas={alphas_seen}")

    # CSV
    if results:
        os.makedirs(os.path.dirname(args.csv), exist_ok=True)
        with open(args.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            w.writeheader()
            w.writerows(results)
        print(f"\nCSV saved to {args.csv}")

    if not args.no_plots and results:
        plot_results(results, PLOTS_DIR)

    return 0


if __name__ == "__main__":
    sys.exit(main())
