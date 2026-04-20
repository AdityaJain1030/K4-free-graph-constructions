#!/usr/bin/env python3
"""
visualizer/plots/plot_10_decision.py
====================================
Plot 10 — the decision plot. For each N, (best greedy c_log − best
known c_log) vs N, coloured by which category achieved the best known
at that N. Horizontal line at gap = 0 and vertical at the "SAT wall"
(largest N with a SAT row in the DB, if any).

Answers: at which scale is each method family winning, and how much
room is there above the best-known floor to the greedy ceiling.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _common import (  # noqa: E402
    CATEGORY_STYLE, category_for, check_sat_available, ensure_img_dir,
)
from graph_db import open_db  # noqa: E402


def main() -> int:
    with open_db() as db:
        rows = db.query(is_k4_free=1)
    has_sat = check_sat_available(rows)

    best_per_n: dict[int, dict] = {}
    greedy_best: dict[int, float] = {}
    for r in rows:
        if r.get("c_log") is None:
            continue
        if r["n"] not in best_per_n or r["c_log"] < best_per_n[r["n"]]["c_log"]:
            best_per_n[r["n"]] = r
        if category_for(r["source"]) == "greedy":
            if r["n"] not in greedy_best or r["c_log"] < greedy_best[r["n"]]:
                greedy_best[r["n"]] = r["c_log"]

    if not greedy_best:
        print("[plot_10] no greedy rows", file=sys.stderr)
        return 1

    sat_wall = None
    if has_sat:
        sat_ns = [r["n"] for r in rows if category_for(r["source"]) == "sat"]
        if sat_ns:
            sat_wall = max(sat_ns)

    ns = sorted(set(greedy_best).intersection(best_per_n))
    x = np.array(ns)
    gap = np.array([greedy_best[n] - best_per_n[n]["c_log"] for n in ns])
    winners = [category_for(best_per_n[n]["source"]) for n in ns]

    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)
    ax.axhline(0, color="black", linewidth=0.7, alpha=0.7)
    if sat_wall is not None:
        ax.axvline(sat_wall, linestyle="--", color="#999", alpha=0.6,
                   label=f"SAT wall (N ≤ {sat_wall})")

    for cat in set(winners):
        color, marker, label = CATEGORY_STYLE.get(cat, CATEGORY_STYLE["other"])
        mask = [w == cat for w in winners]
        ax.scatter(x[mask], gap[mask],
                   s=42, marker=marker,
                   facecolor=color if cat == "sat" else "none",
                   edgecolor=color, linewidth=1.3,
                   label=f"best = {label}  ({sum(mask)})")

    ax.plot(x, gap, color="#999", linewidth=0.8, alpha=0.5, zorder=0)

    ax.set_xlabel("N (vertices)")
    ax.set_ylabel("method gap  (best greedy − best known)")
    ax.set_title("Plot 10 — decision plot: gap vs N, coloured by winning source")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)

    out = os.path.join(ensure_img_dir(), "plot_10_decision.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
