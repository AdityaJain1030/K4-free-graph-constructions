#!/usr/bin/env python3
"""
visualizer/plots/plot_07_degree_variance.py
===========================================
Plot 7 — degree variance of Pareto-optimal graphs vs N.

Pareto-optimality here: min c_log at each (N, d_max) pair — standard
frontier in this project. `d_var` is already cached so no recomputation
is needed.

Horizontal reference at Var(d) = 0.25 — the upper bound for graphs
with degree spread ≤ 1 (the tightest near-regular regime). Graphs
below this line have essentially regular degrees.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _common import CATEGORY_STYLE, category_for, ensure_img_dir  # noqa: E402
from graph_db import open_db  # noqa: E402


def main() -> int:
    with open_db() as db:
        rows = db.query(is_k4_free=1)

    # Pareto-frontier: best c_log per (N, d_max).
    best: dict[tuple[int, int], dict] = {}
    for r in rows:
        if r.get("c_log") is None or r.get("d_var") is None:
            continue
        key = (r["n"], r["d_max"])
        if key not in best or r["c_log"] < best[key]["c_log"]:
            best[key] = r

    if not best:
        print("[plot_07] no Pareto graphs", file=sys.stderr)
        return 1

    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)

    by_cat: dict[str, list[tuple[int, float]]] = {}
    for r in best.values():
        cat = category_for(r["source"])
        by_cat.setdefault(cat, []).append((r["n"], float(r["d_var"])))

    for cat in ("sat", "algebraic", "circulant", "greedy", "blowup", "other"):
        if cat not in by_cat:
            continue
        color, marker, label = CATEGORY_STYLE[cat]
        pts = by_cat[cat]
        ns = [p[0] for p in pts]
        dv = [p[1] for p in pts]
        ax.scatter(ns, dv, s=34, marker=marker,
                   facecolor=color if cat == "sat" else "none",
                   edgecolor=color, linewidth=1.2,
                   alpha=0.85, label=f"{label} ({len(pts)})")

    ax.axhline(0.25, linestyle="--", color="#d62728", alpha=0.6,
               label="Var(d) = 0.25  (tight: degree spread ≤ 1)")
    ax.axhline(1.0, linestyle=":", color="#555", alpha=0.6,
               label="Var(d) = 1")

    ax.set_xlabel("N (vertices)")
    ax.set_ylabel(r"$\mathrm{Var}(d) = N^{-1}\sum (d_i - \bar d)^2$")
    ax.set_title("Plot 7 — degree variance of Pareto-optimal K4-free graphs vs N")
    ax.set_yscale("symlog", linthresh=0.1)
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="upper left", fontsize=9)

    out = os.path.join(ensure_img_dir(), "plot_07_degree_variance.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
