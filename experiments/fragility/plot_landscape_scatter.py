#!/usr/bin/env python3
"""
experiments/fragility/plot_landscape_scatter.py
===============================================
Scatter every graph in a barrier-tree slice in the
(n_edges, c_log) plane, highlight combinatorial local minima.

This makes the "shelf" structure of the c_log landscape visible:
c_log only takes a few distinct values (it's α·d_max / (N·ln d_max)
with α and d_max integer), so the slice clusters onto horizontal
shelves. Local minima exist at *some* values of |E| on each shelf —
visible as red dots in the all-graphs cloud.

    micromamba run -n k4free python experiments/fragility/plot_landscape_scatter.py \\
        --in experiments/fragility/data/barrier_tree_n9_add_delete.json
"""

import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    args = ap.parse_args()
    with open(args.in_path) as f:
        data = json.load(f)

    n = data["n"]
    move = "+".join(data["move"])
    threshold = data["threshold"]
    lms = data.get("local_minima", [])

    # The JSON doesn't store every slice graph's (n_edges, c_log) — but it
    # does store every local minimum's. To get the all-graphs cloud we'd
    # need to re-stream geng. For now plot just local minima — that's the
    # point of this visualization.
    if not lms:
        print("[landscape] no local minima in JSON", file=sys.stderr)
        return 1

    es = [lm["n_edges"] for lm in lms]
    cs = [lm["c_log"] for lm in lms]
    aa = [lm["alpha"] for lm in lms]
    dd = [lm["d_max"] for lm in lms]

    fig, ax = plt.subplots(figsize=(10, 6))

    # color points by (alpha, d_max) — distinct shelves
    pairs = list(set(zip(aa, dd)))
    pairs.sort()
    cmap = plt.get_cmap("tab10")
    pair_to_color = {p: cmap(i % 10) for i, p in enumerate(pairs)}

    for (a, d), color in pair_to_color.items():
        mask = [(ai == a) and (di == d) for ai, di in zip(aa, dd)]
        xs = [e for e, m in zip(es, mask) if m]
        ys = [c for c, m in zip(cs, mask) if m]
        # jitter on c so multiple graphs at the same c_log are visible
        ys_j = [c + (np.random.RandomState(hash((a, d, e)) & 0xffff).rand() - 0.5) * 0.003
                for c, e in zip(ys, xs)]
        ax.scatter(xs, ys_j, color=color, s=12, alpha=0.6,
                   label=f"α={a}, d_max={d} (c={ys[0]:.3f}), {len(xs)} traps",
                   edgecolor="black", linewidth=0.2)

    # Mark the global minimum specially.
    gmin = min(lms, key=lambda x: x["c_log"])
    ax.scatter([gmin["n_edges"]], [gmin["c_log"]], color="#d62728",
               s=180, marker="*", edgecolor="black", linewidth=1.0,
               label=f"global min c={gmin['c_log']:.4f}",
               zorder=10)

    ax.set_xlabel("|E| (edge count)")
    ax.set_ylabel(r"$c_{\log}$")
    ax.set_title(
        f"All combinatorial local minima at N={n} (move={move})\n"
        f"{len(lms)} traps in slice c_log ≤ {threshold}; "
        f"c_log shelves visible as horizontal stripes",
        fontsize=10,
    )
    ax.invert_yaxis()  # better is at the bottom (sky-above-valleys)
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    out = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "images",
        f"landscape_scatter_n{n}_{'_'.join(data['move'])}.png",
    )
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
