#!/usr/bin/env python3
"""
Per-block c vs N plot
=====================
Reads construction_results.csv and block_scan.csv, produces a plot where
each library block's k-copy sweep has its own trajectory, colored by
block parameters (n, α, d_max). Top-5 by min c are highlighted.

Output: c_vs_N_per_block.png
"""

import csv
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.cm as cm

_HERE = os.path.dirname(os.path.abspath(__file__))
CONS_CSV = os.path.join(_HERE, "construction_results.csv")
SCAN_CSV = os.path.join(_HERE, "block_scan.csv")
OUT_PATH = os.path.join(_HERE, "c_vs_N_per_block.png")
FLOOR = 0.9017


def load_scan():
    """Return {block_id: {n, alpha, d_max, source}}."""
    info = {}
    with open(SCAN_CSV, newline="") as f:
        for r in csv.DictReader(f):
            try:
                bid = int(r["block_id"])
                info[bid] = {
                    "n": int(r["n"]),
                    "alpha": int(r["alpha"]),
                    "d_max": int(r["d_max"]),
                    "source": r.get("source", ""),
                    "best_linear_k": int(r.get("best_linear_k", 0) or 0),
                    "num_forced": int(r.get("num_forced", 0) or 0),
                }
            except (ValueError, TypeError):
                continue
    return info


def load_single_runs():
    """Return {block_id: [(N, c), ...]} sorted by N, plus mixed list."""
    by_block = defaultdict(list)
    mixed = []
    with open(CONS_CSV, newline="") as f:
        for r in csv.DictReader(f):
            try:
                N = int(r["N"])
                c = float(r["c"]) if r["c"] not in ("", None) else None
            except (ValueError, TypeError):
                continue
            if c is None:
                continue
            if r["construction"] == "single":
                try:
                    bid = int(r["block_ids"])
                except (ValueError, TypeError):
                    continue
                by_block[bid].append((N, c))
            elif r["construction"] == "mixed":
                mixed.append((N, c))
    for bid in by_block:
        by_block[bid].sort()
    mixed.sort()
    return by_block, mixed


def load_sat_optimal(max_n=35):
    import json
    out = {}
    pareto_dir = os.path.normpath(os.path.join(_HERE, "..", "..", "..",
                                                "SAT_old", "pareto_reference"))
    for N in range(2, max_n + 1):
        path = os.path.join(pareto_dir, f"pareto_n{N}.json")
        if not os.path.isfile(path):
            continue
        with open(path) as f:
            data = json.load(f)
        frontier = [e for e in data.get("pareto_frontier", [])
                    if e.get("c_log") is not None]
        if frontier:
            best = min(frontier, key=lambda e: e["c_log"])
            out[N] = best["c_log"]
    return out


def main():
    info = load_scan()
    by_block, mixed = load_single_runs()
    sat_opt = load_sat_optimal()

    # Best c per block for ranking
    best_per_block = {bid: min(c for _, c in pts) for bid, pts in by_block.items()}
    top5_ids = sorted(best_per_block, key=lambda b: best_per_block[b])[:5]

    # === Figure with 2 panels ===
    fig, axes = plt.subplots(1, 2, figsize=(16, 6), sharey=True)

    # --- Panel 1: all 60 blocks, colored by n (block size) ---
    ax = axes[0]
    block_ns = sorted({info[b]["n"] for b in by_block if b in info})
    n_colors = {n: cm.plasma(i / max(1, len(block_ns) - 1))
                for i, n in enumerate(block_ns)}

    for bid, pts in by_block.items():
        if bid not in info:
            continue
        n_blk = info[bid]["n"]
        xs = [N for N, _ in pts]
        ys = [c for _, c in pts]
        ax.plot(xs, ys, "-", color=n_colors[n_blk], alpha=0.35, linewidth=0.8)

    # Top-5 highlighted
    highlight_colors = plt.cm.tab10.colors
    for i, bid in enumerate(top5_ids):
        pts = by_block[bid]
        m = info.get(bid, {})
        xs = [N for N, _ in pts]
        ys = [c for _, c in pts]
        label = (f"#{bid} n={m.get('n','?')} α={m.get('alpha','?')} "
                 f"d={m.get('d_max','?')} k*={m.get('best_linear_k','?')} "
                 f"min_c={best_per_block[bid]:.4f}")
        ax.plot(xs, ys, "-o", color=highlight_colors[i], markersize=5,
                linewidth=2, label=label)

    if sat_opt:
        xs = sorted(sat_opt)
        ys = [sat_opt[N] for N in xs]
        ax.plot(xs, ys, "--", color="red", linewidth=2, label="SAT-optimal")

    ax.axhline(FLOOR, linestyle="-.", color="purple", alpha=0.6,
               label=f"floor = {FLOOR:.4f}")
    ax.axhline(1.15, linestyle=":", color="gray", label="random ~1.15")

    # Add a light colorbar legend for block-n
    from matplotlib.lines import Line2D
    size_legend = [Line2D([0], [0], color=n_colors[n], lw=2, alpha=0.35,
                          label=f"n={n}") for n in block_ns]
    leg1 = ax.legend(handles=size_legend, title="block size (faint lines)",
                     loc="upper right", fontsize=7)
    ax.add_artist(leg1)
    ax.legend(fontsize=7, loc="lower left")
    ax.set_xlabel("N (total vertices of constructed graph)")
    ax.set_ylabel(r"$c = \alpha \cdot d_{\max} / (N \log d_{\max})$")
    ax.set_title("Per-block c vs N — top 5 highlighted")
    ax.grid(True, alpha=0.3)

    # --- Panel 2: top 5 only, with k_copies shown as x-axis labels ---
    ax = axes[1]
    for i, bid in enumerate(top5_ids):
        pts = by_block[bid]
        m = info.get(bid, {})
        xs = [N for N, _ in pts]
        ys = [c for _, c in pts]
        label = (f"#{bid} (n={m.get('n','?')}, α={m.get('alpha','?')}, "
                 f"d={m.get('d_max','?')}, k*={m.get('best_linear_k','?')})")
        ax.plot(xs, ys, "-o", color=highlight_colors[i], markersize=6,
                linewidth=2, label=label)
        # Annotate each point with k = N / n
        if m.get("n"):
            for x, y in pts:
                k = x // m["n"]
                ax.annotate(f"k={k}", (x, y), fontsize=6, xytext=(3, 3),
                            textcoords="offset points", color=highlight_colors[i])

    if mixed:
        xs = [N for N, _ in mixed]
        ys = [c for _, c in mixed]
        ax.plot(xs, ys, "-s", color="black", markersize=6, linewidth=1.5,
                label="mixed (greedy)")

    if sat_opt:
        xs = sorted(sat_opt)
        ys = [sat_opt[N] for N in xs]
        ax.plot(xs, ys, "--", color="red", linewidth=2, label="SAT-optimal")

    ax.axhline(FLOOR, linestyle="-.", color="purple", alpha=0.6,
               label=f"floor = {FLOOR:.4f}")

    ax.set_xlabel("N")
    ax.set_title("Top-5 blocks — detailed trajectories (k = N/n annotated)")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=8, loc="best")

    fig.suptitle("Forced-matching: c vs N per-block (each line is one library block × k=2..12)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=120)
    plt.close(fig)
    print(f"Wrote {OUT_PATH}")

    # Also print top-5 as a small text summary
    print("\nTop-5 blocks by min c:")
    for bid in top5_ids:
        m = info.get(bid, {})
        print(f"  #{bid:5d} n={m.get('n','?')} α={m.get('alpha','?')} "
              f"d={m.get('d_max','?')} k*={m.get('best_linear_k','?')} "
              f"min_c={best_per_block[bid]:.4f} "
              f"(swept {len(by_block[bid])} values)")


if __name__ == "__main__":
    main()
