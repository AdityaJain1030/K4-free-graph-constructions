#!/usr/bin/env python3
"""
experiments/alpha/bench_alpha_accuracy.py
==========================================
Benchmarks how well cheap alpha proxies (Caro-Wei, greedy MIS, clique UB)
track the true independence number across all K4-free graph classes defined
in generate_graphs.py.

Proxies measured
----------------
  caro_wei       deterministic lower bound: sum_v 1/(d(v)+1)
  greedy_mis     random-restart greedy MIS, R restarts (alpha_lb)
  clique_ub      greedy clique-cover upper bound (alpha_ub)

True alpha
----------
  alpha_bb_clique_cover  (project default; used as ground truth for proxy error)

Outputs
-------
  results/accuracy_results.csv   per-graph raw numbers
  results/accuracy_plots/        one plot per metric

Usage
-----
    micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py
    micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py \\
        --classes prime_circulant sat_exact random_k4free
    micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py --restarts 100
    micromamba run -n k4free python experiments/alpha/bench_alpha_accuracy.py --no-plots
"""

from __future__ import annotations

import argparse
import csv
import math
import multiprocessing as mp
import os
import resource
import sys
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import spearmanr

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

from experiments.alpha.generate_graphs import load_all, ALL_CLASSES
from utils.graph_props import alpha_bb_clique_cover
from utils.alpha_surrogate import alpha_lb, alpha_ub

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "results")
PLOTS_DIR   = os.path.join(RESULTS_DIR, "accuracy_plots")

CLASS_ORDER = list(ALL_CLASSES)
COLORS = {
    "prime_circulant":  "#1f77b4",
    "dihedral_cayley":  "#ff7f0e",
    "polarity":         "#2ca02c",
    "random_k4free":    "#d62728",
    "brown":            "#9467bd",
    "sat_exact":        "#8c564b",
    "near_regular":     "#e377c2",
}


# ---------------------------------------------------------------------------
# Caro-Wei bound (O(n), degree-based)
# ---------------------------------------------------------------------------

def caro_wei(G) -> float:
    return sum(1.0 / (d + 1) for _, d in G.degree())


# ---------------------------------------------------------------------------
# Per-graph worker (run in subprocess for isolated RSS measurement)
# ---------------------------------------------------------------------------

def _worker(args):
    import resource, time
    G, restarts = args
    adj = np.array(__import__("networkx").to_numpy_array(G, dtype=np.uint8))
    deg = adj.sum(axis=1)

    results = {}

    # Caro-Wei
    results["caro_wei"] = sum(1.0 / (d + 1) for d in deg)

    # Greedy MIS lower bound
    rng = np.random.default_rng(42)
    t0 = time.perf_counter()
    results["greedy_mis"] = alpha_lb(adj, restarts=restarts, rng=rng)
    results["greedy_time"] = time.perf_counter() - t0

    # Clique upper bound
    results["clique_ub"] = alpha_ub(adj)

    # True alpha via bb_clique_cover (ground truth for proxy error)
    t0 = time.perf_counter()
    exact, _ = alpha_bb_clique_cover(adj)
    results["exact_time"] = time.perf_counter() - t0
    results["alpha_exact"] = exact

    results["peak_rss_mb"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

    return results


# ---------------------------------------------------------------------------
# Main benchmark loop
# ---------------------------------------------------------------------------

def run_benchmark(graphs: list[dict], restarts: int, timeout: float) -> list[dict]:
    rows = []
    n_total = len(graphs)
    for i, g in enumerate(graphs):
        G   = g["graph"]
        n   = g["n"]
        cls = g["class"]
        lbl = g["label"]
        print(f"  [{i+1:3d}/{n_total}] {cls:20s} {lbl:30s} n={n}", end=" ", flush=True)

        ctx = mp.get_context("fork")
        q   = ctx.Queue()

        def _target(args, q):
            try:
                q.put(_worker(args))
            except Exception as e:
                q.put({"error": str(e)})

        p = ctx.Process(target=_target, args=((G, restarts), q))
        p.start()
        p.join(timeout)

        if p.is_alive():
            p.terminate(); p.join()
            print(f"TIMEOUT ({timeout}s)")
            continue

        if q.empty():
            print("ERROR (no result)")
            continue

        res = q.get()
        if "error" in res:
            print(f"ERROR: {res['error']}")
            continue

        alpha_true = res["alpha_exact"]
        cw         = res["caro_wei"]
        greedy     = res["greedy_mis"]
        ub         = res["clique_ub"]

        cw_err     = alpha_true - cw
        greedy_err = alpha_true - greedy
        ub_err     = ub - alpha_true
        cw_rel     = cw_err / alpha_true if alpha_true else None
        greedy_rel = greedy_err / alpha_true if alpha_true else None

        print(f"α={alpha_true:3d}  cw={cw:.1f}(err={cw_err:+.1f})  "
              f"greedy={greedy}(err={greedy_err:+d})  "
              f"exact={res['exact_time']*1000:.1f}ms")

        row = {
            "class":          cls,
            "label":          lbl,
            "n":              n,
            "alpha_exact":    alpha_true,
            "caro_wei":       round(cw, 4),
            "greedy_mis":     greedy,
            "clique_ub":      ub,
            "cw_abs_err":     round(cw_err, 4),
            "cw_rel_err":     round(cw_rel, 4) if cw_rel is not None else None,
            "greedy_abs_err": greedy_err,
            "greedy_rel_err": round(greedy_rel, 4) if greedy_rel is not None else None,
            "ub_abs_err":     ub_err,
            "exact_time_ms":  round(res["exact_time"] * 1000, 2),
            "greedy_time_ms": round(res["greedy_time"] * 1000, 2),
            "peak_rss_mb":    round(res["peak_rss_mb"], 1),
            "c_log":          g.get("c_log"),
        }
        rows.append(row)

    return rows


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------

def make_plots(rows: list[dict], out_dir: str):
    os.makedirs(out_dir, exist_ok=True)

    by_class: dict[str, list[dict]] = {}
    for r in rows:
        by_class.setdefault(r["class"], []).append(r)

    # --- 1. Spearman ρ per class (greedy vs caro-wei vs clique_ub) ---
    fig, ax = plt.subplots(figsize=(10, 5))
    classes = [c for c in CLASS_ORDER if c in by_class]
    x = np.arange(len(classes))
    w = 0.25

    rho_greedy, rho_cw, rho_ub = [], [], []
    for cls in classes:
        data = by_class[cls]
        true_a  = [d["alpha_exact"] for d in data]
        greedy  = [d["greedy_mis"]  for d in data]
        cw      = [d["caro_wei"]    for d in data]
        ub      = [d["clique_ub"]   for d in data]
        rho_greedy.append(spearmanr(true_a, greedy).statistic if len(data) > 2 else float("nan"))
        rho_cw.append(    spearmanr(true_a, cw).statistic     if len(data) > 2 else float("nan"))
        rho_ub.append(    spearmanr(true_a, ub).statistic     if len(data) > 2 else float("nan"))

    ax.bar(x - w, rho_greedy, w, label="Greedy MIS", color="#2ca02c")
    ax.bar(x,     rho_cw,     w, label="Caro-Wei",   color="#d62728")
    ax.bar(x + w, rho_ub,     w, label="Clique UB",  color="#1f77b4")
    ax.set_xticks(x)
    ax.set_xticklabels(classes, rotation=25, ha="right")
    ax.set_ylabel("Spearman ρ vs true α")
    ax.set_ylim(-0.1, 1.05)
    ax.axhline(1.0, color="k", lw=0.5, ls="--")
    ax.set_title("Proxy ranking accuracy by graph class")
    ax.legend()
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "spearman_by_class.png"), dpi=150)
    plt.close(fig)

    # --- 2. Relative error vs n (greedy and caro-wei) ---
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for cls in classes:
        data  = sorted(by_class[cls], key=lambda d: d["n"])
        ns    = [d["n"] for d in data]
        c_err = [d["cw_rel_err"] for d in data]
        g_err = [d["greedy_rel_err"] for d in data]
        col   = COLORS.get(cls, "gray")
        axes[0].plot(ns, c_err, "o-", label=cls, color=col, markersize=4)
        axes[1].plot(ns, g_err, "o-", label=cls, color=col, markersize=4)

    for ax, title in zip(axes, ["Caro-Wei relative error", "Greedy MIS relative error"]):
        ax.axhline(0, color="k", lw=0.5, ls="--")
        ax.set_xlabel("n")
        ax.set_ylabel("(true α − proxy) / true α")
        ax.set_title(title)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "relative_error_vs_n.png"), dpi=150)
    plt.close(fig)

    # --- 3. Solver wall time vs n per class ---
    fig, ax = plt.subplots(figsize=(10, 5))
    for cls in classes:
        data = sorted(by_class[cls], key=lambda d: d["n"])
        ns   = [d["n"] for d in data]
        ts   = [d["exact_time_ms"] for d in data]
        col  = COLORS.get(cls, "gray")
        ax.semilogy(ns, ts, "o-", label=cls, color=col, markersize=4)
    ax.set_xlabel("n")
    ax.set_ylabel("Wall time (ms, log scale)")
    ax.set_title("alpha_bb_clique_cover wall time by graph class")
    ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "solver_time_by_class.png"), dpi=150)
    plt.close(fig)

    # --- 4. Greedy MIS absolute error distribution per class ---
    fig, ax = plt.subplots(figsize=(10, 5))
    errs = [
        [d["greedy_abs_err"] for d in by_class[cls]]
        for cls in classes if cls in by_class
    ]
    ax.boxplot(errs, labels=classes, vert=True)
    ax.set_ylabel("|true α − greedy MIS|")
    ax.set_title("Greedy MIS absolute error distribution")
    plt.xticks(rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "greedy_error_dist.png"), dpi=150)
    plt.close(fig)

    # --- 5. Proxy vs true α scatter (one panel per proxy) ---
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    proxy_keys   = ["caro_wei",  "greedy_mis",  "clique_ub"]
    proxy_labels = ["Caro-Wei",  "Greedy MIS",  "Clique UB"]
    proxy_dirs   = ["lb",        "lb",          "ub"]   # lb = underestimate, ub = overestimate

    for ax, key, label, direction in zip(axes, proxy_keys, proxy_labels, proxy_dirs):
        for cls in classes:
            data   = by_class[cls]
            true_a = [d["alpha_exact"] for d in data]
            proxy  = [d[key]           for d in data]
            col    = COLORS.get(cls, "gray")
            ax.scatter(true_a, proxy, label=cls, color=col, s=18, alpha=0.8)

        all_true = [d["alpha_exact"] for d in rows]
        lo, hi   = min(all_true) * 0.9, max(all_true) * 1.05
        ax.plot([lo, hi], [lo, hi], "k--", lw=0.8, label="y=x (perfect)")
        ax.set_xlabel("True α")
        ax.set_ylabel(f"{label}")
        ax.set_title(f"{label} vs true α")
        if direction == "lb":
            ax.fill_between([lo, hi], [lo, hi], [hi, hi], alpha=0.04, color="red",
                            label="overestimate region")
        else:
            ax.fill_between([lo, hi], [lo, lo], [lo, hi], alpha=0.04, color="red",
                            label="underestimate region")
        ax.legend(fontsize=6)

    fig.suptitle("Proxy accuracy: scatter against true α (all graph classes)", y=1.01)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "proxy_scatter.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)

    # --- 6. AlphaBracket relative width vs n per class ---
    # Normalise by true α so the y-axis is interpretable across different n.
    # Points at y=0 mean the bracket certifies exact α without SAT.
    fig, ax = plt.subplots(figsize=(10, 5))
    for cls in classes:
        data = by_class[cls]
        col  = COLORS.get(cls, "gray")
        xs, ys = [], []
        for d in data:
            true_a = d["alpha_exact"]
            if true_a > 0:
                xs.append(d["n"])
                ys.append((d["clique_ub"] - d["greedy_mis"]) / true_a)
        ax.scatter(xs, ys, label=cls, color=col, s=30, alpha=0.8, zorder=3)
    ax.axhline(0, color="k", lw=0.8, ls="--", label="0  (bracket certifies exact α)")
    ax.set_xlabel("n")
    ax.set_ylabel("(clique_ub − greedy_mis) / α  (relative bracket width)")
    ax.set_title("AlphaBracket relative width — points at 0 need no SAT call")
    ax.legend(fontsize=7)
    ax.set_ylim(bottom=-0.05)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "bracket_width.png"), dpi=150)
    plt.close(fig)

    # --- 7. Exact-match rate (greedy == true α) by class ---
    fig, ax = plt.subplots(figsize=(9, 4))
    exact_rates = []
    for cls in classes:
        data  = by_class[cls]
        rate  = 100 * sum(d["greedy_abs_err"] == 0 for d in data) / len(data)
        exact_rates.append(rate)
        col   = COLORS.get(cls, "gray")
    bars = ax.bar(classes, exact_rates,
                  color=[COLORS.get(c, "gray") for c in classes])
    ax.set_ylabel("% graphs where greedy MIS == true α")
    ax.set_ylim(0, 105)
    ax.axhline(100, color="k", lw=0.5, ls="--")
    ax.set_title("Greedy MIS exact-match rate by graph class")
    for bar, rate in zip(bars, exact_rates):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                f"{rate:.0f}%", ha="center", va="bottom", fontsize=9)
    plt.xticks(rotation=25, ha="right")
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "exact_match_rate.png"), dpi=150)
    plt.close(fig)

    print(f"\n  Plots saved to {out_dir}/")


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary(rows: list[dict]):
    by_class: dict[str, list[dict]] = {}
    for r in rows:
        by_class.setdefault(r["class"], []).append(r)

    print("\n" + "="*90)
    print(f"{'Class':<22} {'N graphs':>8} {'N range':>14} "
          f"{'ρ(greedy)':>10} {'ρ(CW)':>8} {'greedy err=0%':>14} {'median t(ms)':>13}")
    print("-"*90)

    for cls in CLASS_ORDER:
        if cls not in by_class:
            continue
        data   = by_class[cls]
        true_a = [d["alpha_exact"] for d in data]
        greedy = [d["greedy_mis"]  for d in data]
        cw     = [d["caro_wei"]    for d in data]
        times  = [d["exact_time_ms"] for d in data]
        ns     = [d["n"] for d in data]

        rho_g  = spearmanr(true_a, greedy).statistic if len(data) > 2 else float("nan")
        rho_c  = spearmanr(true_a, cw).statistic     if len(data) > 2 else float("nan")
        exact_pct = 100 * sum(g == a for g, a in zip(greedy, true_a)) / len(data)
        med_t  = sorted(times)[len(times) // 2]

        print(f"  {cls:<20} {len(data):>8} {min(ns):>5}..{max(ns):<5}   "
              f"{rho_g:>9.3f}  {rho_c:>7.3f}  {exact_pct:>12.0f}%  {med_t:>11.1f}")
    print("="*90)


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------

def save_csv(rows: list[dict], path: str):
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"  CSV saved to {path}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Benchmark alpha proxy accuracy across K4-free graph classes.")
    parser.add_argument("--classes", nargs="+", choices=list(ALL_CLASSES),
                        help="Graph classes to include (default: all)")
    parser.add_argument("--restarts", type=int, default=32,
                        help="Greedy MIS restarts (default: 32)")
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="Per-graph timeout in seconds (default: 60)")
    parser.add_argument("--no-plots", action="store_true",
                        help="Skip plot generation")
    args = parser.parse_args()

    print("Loading graphs...")
    graphs = load_all(args.classes)
    print(f"  {len(graphs)} graphs loaded\n")

    print("Running benchmark:")
    rows = run_benchmark(graphs, restarts=args.restarts, timeout=args.timeout)

    print_summary(rows)

    csv_path = os.path.join(RESULTS_DIR, "accuracy_results.csv")
    save_csv(rows, csv_path)

    if not args.no_plots:
        make_plots(rows, PLOTS_DIR)
