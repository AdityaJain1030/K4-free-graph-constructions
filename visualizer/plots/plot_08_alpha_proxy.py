#!/usr/bin/env python3
"""
visualizer/plots/plot_08_alpha_proxy.py
=======================================
Plot 8 — α proxy quality. For each graph where we have exact α
(cached α is computed via alpha_bb_clique_cover, which is exact), run
a fast greedy approximation and scatter greedy-α vs true α.

The greedy-α is recomputed on the fly (the cache only stores the exact
value). Runs on up to `--max-graphs` random rows to keep wall time
bounded.
"""

import argparse
import os
import random
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import networkx as nx  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _common import CATEGORY_STYLE, category_for, ensure_img_dir  # noqa: E402
from graph_db import open_db  # noqa: E402
from utils.graph_props import alpha_approx  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-graphs", type=int, default=200)
    ap.add_argument("--restarts", type=int, default=200)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    with open_db() as db:
        rows = db.query(is_k4_free=1)
        rows = [r for r in rows
                if r.get("alpha") is not None and r.get("n") is not None]
        rng = random.Random(args.seed)
        if len(rows) > args.max_graphs:
            rows = rng.sample(rows, args.max_graphs)
        hydrated = db.hydrate(rows)

    if not hydrated:
        print("[plot_08] no hydrated rows", file=sys.stderr)
        return 1

    points: list[tuple[int, int, str]] = []
    for rec in hydrated:
        adj = rec["adj"]
        true_a = rec["alpha"]
        approx_a = alpha_approx(adj, restarts=args.restarts)
        points.append((true_a, approx_a, rec["source"]))

    fig, (ax_scatter, ax_hist) = plt.subplots(
        1, 2, figsize=(13, 5.5), constrained_layout=True,
        gridspec_kw={"width_ratios": [1.4, 1]},
    )

    by_cat: dict[str, list[tuple[int, int]]] = {}
    for t, a, src in points:
        by_cat.setdefault(category_for(src), []).append((t, a))

    max_a = max(p[0] for p in points)
    ax_scatter.plot([0, max_a], [0, max_a], linestyle="--", color="black",
                    alpha=0.6, label="y = x  (perfect)")

    for cat in ("sat", "algebraic", "circulant", "greedy", "blowup", "other"):
        if cat not in by_cat:
            continue
        color, marker, label = CATEGORY_STYLE[cat]
        pts = by_cat[cat]
        xs = [p[0] + rng.uniform(-0.15, 0.15) for p in pts]
        ys = [p[1] + rng.uniform(-0.15, 0.15) for p in pts]
        ax_scatter.scatter(xs, ys, s=28, marker=marker,
                           facecolor=color if cat == "sat" else "none",
                           edgecolor=color, linewidth=1.0, alpha=0.85,
                           label=f"{label} ({len(pts)})")

    ax_scatter.set_xlabel(r"true $\alpha$  (exact B&B clique-cover)")
    ax_scatter.set_ylabel(r"greedy $\alpha$ approximation")
    ax_scatter.set_title("greedy α vs true α  (jittered)")
    ax_scatter.grid(alpha=0.3)
    ax_scatter.legend(loc="upper left", fontsize=8)
    ax_scatter.set_aspect("equal", adjustable="box")

    diffs = np.array([true - appx for true, appx, _ in points])
    ax_hist.hist(diffs, bins=np.arange(diffs.min() - 0.5, diffs.max() + 1.5, 1),
                 color="#1f77b4", alpha=0.75, edgecolor="black")
    ax_hist.axvline(0, color="black", linewidth=0.8)
    ax_hist.set_xlabel(r"$\alpha_{\text{true}} - \alpha_{\text{greedy}}$")
    ax_hist.set_ylabel("count")
    ax_hist.set_title(f"gap histogram  (mean={diffs.mean():.2f}, max={diffs.max()})")
    ax_hist.grid(alpha=0.3)

    fig.suptitle(
        f"Plot 8 — α proxy quality  ({len(points)} graphs, "
        f"restarts={args.restarts})"
    )

    out = os.path.join(ensure_img_dir(), "plot_08_alpha_proxy.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
