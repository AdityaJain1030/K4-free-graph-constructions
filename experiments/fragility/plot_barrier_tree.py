#!/usr/bin/env python3
"""
experiments/fragility/plot_barrier_tree.py
==========================================
Render the disconnectivity graph / barrier tree from
run_barrier_tree.py output.

Two figures:
  * `<stem>_dendrogram.png`: classic barrier tree, x = local minima
    (sorted by c_log), y = c_log; horizontal lines join two minima at
    the saddle level where their components merge.
  * `<stem>_components_vs_clog.png`: number of disconnected components
    of the move graph as c_log threshold rises. Strictly nonincreasing
    after the first local min.

    micromamba run -n k4free python experiments/fragility/plot_barrier_tree.py \\
        --in experiments/fragility/data/barrier_tree_n8_switch.json
"""

import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def _build_dendrogram_layout(local_minima: list[dict],
                             saddles: list[dict]) -> dict:
    """Position each local minimum on a 1D x-axis. We use a
    Boruvka/UPGMA-style placement: each saddle defines two clusters
    that get merged; their joint x is the average of the two cluster
    centroids weighted by basin size.

    Returns:
      x_pos: dict {gid -> float}        — x-coordinates of leaves
      merges: list of (level, x1, x2, y_top) — the horizontal U-shapes
    """
    if not local_minima:
        return {"x_pos": {}, "merges": [], "leaves": []}

    # Initial: place leaves in c_log order on integer x-coords
    sorted_lm = sorted(local_minima, key=lambda m: m["c_log"])
    x_pos = {lm["gid"]: float(i) for i, lm in enumerate(sorted_lm)}
    cluster_x: dict[str, float] = dict(x_pos)
    # use 'size' (component size) if present, else 'basin_size'
    cluster_size: dict[str, int] = {lm["gid"]: lm.get("size",
                                                      lm.get("basin_size", 1))
                                    for lm in sorted_lm}

    # Union-find over leaves
    parent = {lm["gid"]: lm["gid"] for lm in sorted_lm}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    merges = []
    for s in sorted(saddles, key=lambda s: s["level"]):
        a, b = s["merged_min_a"], s["merged_min_b"]
        if a not in parent or b not in parent:
            continue
        ra = find(a)
        rb = find(b)
        if ra == rb:
            continue
        xa, xb = cluster_x[ra], cluster_x[rb]
        sa, sb = cluster_size[ra], cluster_size[rb]
        new_x = (xa * sa + xb * sb) / (sa + sb)
        merges.append({
            "level": s["level"],
            "x_left": min(xa, xb),
            "x_right": max(xa, xb),
        })
        # union
        parent[rb] = ra
        cluster_x[ra] = new_x
        cluster_size[ra] = sa + sb

    return {"x_pos": x_pos, "merges": merges, "leaves": sorted_lm}


def plot_dendrogram(data: dict, out_path: str) -> None:
    n = data["n"]
    move = "+".join(data["move"])
    # Use connected-component reps as dendrogram leaves (saddle merges
    # in the Kruskal algorithm act on these, not on combinatorial minima).
    lms = data.get("components") or data["local_minima"]
    saddles = data["saddles"]
    threshold = data["threshold"]

    layout = _build_dendrogram_layout(lms, saddles)
    leaves = layout["leaves"]

    if not leaves:
        return
    fig, ax = plt.subplots(figsize=(max(7, 0.3 * len(leaves)), 5.5))

    # leaf vertical stems from c_log down to figure top
    sizes = [lm.get("size", lm.get("basin_size", 1)) for lm in leaves]
    max_size = max(sizes) if sizes else 1
    for lm, sz in zip(leaves, sizes):
        x = layout["x_pos"][lm["gid"]]
        cl = lm["c_log"]
        ax.plot([x, x], [cl, threshold], color="#1f77b4",
                linewidth=0.7, alpha=0.5)
        # marker at leaf
        ax.scatter([x], [cl], color="#1f77b4", s=12, zorder=5,
                   edgecolor="black", linewidth=0.3)
        if sz >= max(2, max_size * 0.05):
            ax.text(x, cl, f"|B|={sz}",
                    fontsize=6, ha="left", va="bottom",
                    rotation=0, color="#444")

    # horizontal merge bars
    for m in layout["merges"]:
        ax.plot([m["x_left"], m["x_right"]],
                [m["level"], m["level"]],
                color="#444", linewidth=0.9, alpha=0.85)

    ax.set_xlabel("local minima (sorted by c_log)")
    ax.set_ylabel(r"$c_{\log}$")
    ax.set_xticks([])
    # invert y so lowest c_log at the bottom (visually like an energy landscape)
    ax.set_ylim(threshold, min(lm["c_log"] for lm in leaves) * 0.99)
    ax.invert_yaxis()
    ax.set_title(
        f"Barrier tree at N={n}, move={move}, threshold {threshold}\n"
        f"{len(leaves)} local minima, slice size {data['slice_size']}",
        fontsize=10,
    )
    ax.grid(alpha=0.2, axis="y")
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def plot_components_curve(data: dict, out_path: str) -> None:
    bt = data["barrier_tree"]
    if not bt:
        return
    cls = [r["c_log"] for r in bt]
    ncs = [r["n_components"] for r in bt]

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.step(cls, ncs, where="post", color="#1f77b4")
    ax.set_xlabel(r"$c_{\log}$")
    ax.set_ylabel("number of move-graph components in slice")
    ax.set_title(f"Components vs c_log threshold at N={data['n']} "
                 f"(move={'+'.join(data['move'])})")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def plot_local_minima_histogram(data: dict, out_path: str) -> None:
    """Distribution of c_log values across all combinatorial local minima.
    The 'trap density' as a function of c_log — descent from a random init
    will tend to terminate at one of these graphs."""
    lms = data.get("local_minima", [])
    if not lms:
        return
    cls = sorted([lm["c_log"] for lm in lms])
    fig, ax = plt.subplots(figsize=(9, 4.5))
    bins = np.linspace(min(cls) * 0.99, max(cls) * 1.01, 60)
    ax.hist(cls, bins=bins, color="#d62728", alpha=0.7, edgecolor="black",
            linewidth=0.4)
    ax.set_xlabel(r"$c_{\log}$")
    ax.set_ylabel("# combinatorial local minima at this c_log")
    ax.set_title(f"Trap density at N={data['n']} "
                 f"(move={'+'.join(data['move'])}): "
                 f"{len(lms)} graphs are best-improving descent endpoints "
                 f"in the slice")
    ax.grid(alpha=0.3)
    # annotate the global minimum
    ax.axvline(min(cls), color="#1f77b4", linewidth=1.2, linestyle="--",
               label=f"global min c_log={min(cls):.4f}")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(out_path, dpi=160, bbox_inches="tight")
    print(f"wrote {out_path}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    args = ap.parse_args()
    with open(args.in_path) as f:
        data = json.load(f)
    img_dir = os.path.join(HERE, "images")
    os.makedirs(img_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(args.in_path))[0]
    plot_dendrogram(data, os.path.join(img_dir, f"{stem}_dendrogram.png"))
    plot_components_curve(data, os.path.join(img_dir, f"{stem}_components.png"))
    plot_local_minima_histogram(data, os.path.join(img_dir, f"{stem}_traps.png"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
