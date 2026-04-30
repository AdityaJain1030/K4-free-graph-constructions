"""
experiments/edge_gradients/plot_sweep.py
========================================
Multi-N plots from sweep_results.csv + sweep_summary.csv.

Produces:
  sweep_trajectories.png   — α(t) per method, faceted by N. Shows whether
                             the saddle-escape pattern at N=20 holds across
                             N values.
  sweep_escape_rate.png    — bar chart of saddle-escape rate (fraction of
                             trials with α drop > 0) per (method, N).
  sweep_alpha_drop.png     — mean α drop per (method, N) — same as escape
                             rate but shows magnitude, not just success.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np


HERE = os.path.dirname(os.path.abspath(__file__))


METHODS = [
    ("random",          "random",                            "C7"),
    ("drop_alpha",      r"drop-$\alpha$ (exact)",            "C0"),
    ("drop_e_max",      r"drop-$E_{\max}$ (global)",         "C1"),
    ("drop_l_hc",       r"drop-$L_{HC}$ (local)",            "C5"),
    ("hardcore_comarg", r"$\rho_{uw}$ (hardcore co-marginal)","C2"),
    ("sdp_X_uw",        r"$X_{uw}$ (SDP $\vartheta$)",       "C3"),
    ("lp_xu_plus_xw",   r"LP slack",                         "C4"),
    ("hoffman_grad",    r"Hoffman $\nabla$",                 "C6"),
]


def f(s):
    return float(s) if s not in ("", "None") else None


def load(path):
    with open(path) as h:
        return list(csv.DictReader(h))


def trajectory_panel(ax, rows, n_value, methods_present):
    """α(t) per method on one panel for fixed N."""
    grouped = defaultdict(list)
    for r in rows:
        if int(r["n"]) != n_value or int(r["skipped"]):
            continue
        grouped[(r["method"], int(r["t"]))].append(int(r["alpha"]))

    seen_any = False
    for method, label, color in METHODS:
        if method not in methods_present:
            continue
        ts = sorted({int(r["t"]) for r in rows
                     if r["method"] == method and int(r["n"]) == n_value
                     and not int(r["skipped"])})
        means, stds = [], []
        valid_ts = []
        for t in ts:
            vs = grouped.get((method, t), [])
            if not vs:
                continue
            means.append(statistics.mean(vs))
            stds.append(statistics.stdev(vs) if len(vs) > 1 else 0.0)
            valid_ts.append(t)
        if not means:
            continue
        seen_any = True
        ax.plot(valid_ts, means, color=color, lw=1.7, label=label,
                marker="o", ms=2.5)
        ax.fill_between(valid_ts,
                        [m - s for m, s in zip(means, stds)],
                        [m + s for m, s in zip(means, stds)],
                        color=color, alpha=0.10)
    ax.set_xlabel(r"$t$")
    ax.set_ylabel(r"avg $\alpha$")
    ax.set_title(f"$N = {n_value}$")
    ax.grid(True, alpha=0.3)
    return seen_any


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(HERE, "sweep_results.csv"))
    ap.add_argument("--summary", default=os.path.join(HERE, "sweep_summary.csv"))
    ap.add_argument("--out-dir", default=HERE)
    args = ap.parse_args()

    rows = load(args.results)
    summary = load(args.summary)

    ns = sorted({int(r["n"]) for r in rows})
    methods_present = {r["method"] for r in rows
                       if not int(r["skipped"])}
    print(f"[plot_sweep] N values: {ns}")
    print(f"[plot_sweep] methods present (any N): {sorted(methods_present)}")

    # ---------- 1. Trajectory grid ----------
    cols = min(len(ns), 4)
    rows_grid = (len(ns) + cols - 1) // cols
    fig, axes = plt.subplots(rows_grid, cols,
                             figsize=(5.0 * cols, 3.5 * rows_grid),
                             squeeze=False)
    for i, n_val in enumerate(ns):
        ax = axes[i // cols][i % cols]
        trajectory_panel(ax, rows, n_val, methods_present)
    for j in range(len(ns), rows_grid * cols):
        axes[j // cols][j % cols].axis("off")

    handles, labels = axes[0][0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4,
               frameon=False, fontsize=9, bbox_to_anchor=(0.5, -0.02))
    fig.suptitle("Saddle-escape α(t) per method, faceted by N "
                 "(sweep over α-flat starting graphs)", fontsize=11)
    fig.tight_layout(rect=[0, 0.06, 1, 0.97])
    out_path = os.path.join(args.out_dir, "sweep_trajectories.png")
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[plot_sweep] wrote {out_path}")

    # ---------- 2. Saddle-escape rate ----------
    by_mn = defaultdict(list)
    for s in summary:
        if int(s["skipped"]):
            continue
        by_mn[(s["method"], int(s["n"]))].append(int(s["alpha_drop"]) > 0)

    fig, ax = plt.subplots(figsize=(11, 5))
    methods_visible = [m for m, _, _ in METHODS if m in methods_present]
    width = 0.8 / len(ns)
    x = np.arange(len(methods_visible))
    for i, n_val in enumerate(ns):
        rates = []
        for m in methods_visible:
            v = by_mn.get((m, n_val), [])
            rates.append(sum(v) / len(v) if v else 0.0)
        ax.bar(x + i * width - 0.4 + width / 2, rates, width=width,
               label=f"N={n_val}")
    ax.set_xticks(x)
    ax.set_xticklabels([dict([(m, lab) for m, lab, _ in METHODS])[m]
                        for m in methods_visible],
                       rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("saddle-escape rate (α dropped at least once)")
    ax.set_ylim(0, 1.05)
    ax.set_title("Saddle escape rate by method and N")
    ax.legend(ncol=len(ns), loc="lower right", frameon=False)
    ax.grid(True, axis="y", alpha=0.3)
    out_path = os.path.join(args.out_dir, "sweep_escape_rate.png")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[plot_sweep] wrote {out_path}")

    # ---------- 3. Mean α drop ----------
    by_mn_mag = defaultdict(list)
    for s in summary:
        if int(s["skipped"]):
            continue
        by_mn_mag[(s["method"], int(s["n"]))].append(int(s["alpha_drop"]))

    fig, ax = plt.subplots(figsize=(11, 5))
    for i, n_val in enumerate(ns):
        means = []
        for m in methods_visible:
            v = by_mn_mag.get((m, n_val), [])
            means.append(statistics.mean(v) if v else 0.0)
        ax.bar(x + i * width - 0.4 + width / 2, means, width=width,
               label=f"N={n_val}")
    ax.set_xticks(x)
    ax.set_xticklabels([dict([(m, lab) for m, lab, _ in METHODS])[m]
                        for m in methods_visible],
                       rotation=20, ha="right", fontsize=9)
    ax.set_ylabel("mean α drop after T steps")
    ax.set_title("Mean total α drop by method and N")
    ax.legend(ncol=len(ns), loc="upper right", frameon=False)
    ax.grid(True, axis="y", alpha=0.3)
    out_path = os.path.join(args.out_dir, "sweep_alpha_drop.png")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"[plot_sweep] wrote {out_path}")


if __name__ == "__main__":
    main()
