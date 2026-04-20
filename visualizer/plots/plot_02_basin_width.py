#!/usr/bin/env python3
"""
visualizer/plots/plot_02_basin_width.py
=======================================
Plot 2 — basin width. Violin / box plot per N of c_log values from the
greedy sources (``random``, ``random_regular_switch``, ``regularity``).
Overlay the SAT-optimal c_log per N as a red dot (skipped + logged
if no SAT rows in the DB).

Narrow violins whose lower whiskers approach the red dot = basin is
concentrating and unsophisticated search is increasingly sufficient.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _common import category_for, check_sat_available, ensure_img_dir  # noqa: E402
from graph_db import open_db  # noqa: E402


def main() -> int:
    with open_db() as db:
        rows = db.query(is_k4_free=1)

    greedy = [r for r in rows if category_for(r["source"]) == "greedy"
              and r.get("c_log") is not None]
    if not greedy:
        print("[plot_02] no greedy-source rows", file=sys.stderr)
        return 1

    by_n: dict[int, list[float]] = {}
    for r in greedy:
        by_n.setdefault(r["n"], []).append(r["c_log"])

    ns = sorted(by_n)
    data = [by_n[n] for n in ns]

    has_sat = check_sat_available(rows)
    sat_per_n: dict[int, float] = {}
    if has_sat:
        for r in rows:
            if category_for(r["source"]) == "sat" and r.get("c_log") is not None:
                if r["n"] not in sat_per_n or r["c_log"] < sat_per_n[r["n"]]:
                    sat_per_n[r["n"]] = r["c_log"]

    fig, ax = plt.subplots(figsize=(11, 5.5), constrained_layout=True)

    # Violin plot. matplotlib violins need positions in the same units as
    # the x axis so we place them at the true N values.
    parts = ax.violinplot(
        data, positions=ns, widths=[max(1.0, n * 0.08) for n in ns],
        showmeans=False, showmedians=True, showextrema=True,
    )
    for pc in parts["bodies"]:
        pc.set_facecolor("#2ca02c")
        pc.set_alpha(0.35)
        pc.set_edgecolor("#1f5e1f")
    for key in ("cmedians", "cmins", "cmaxes", "cbars"):
        if key in parts:
            parts[key].set_color("#1f5e1f")
            parts[key].set_linewidth(1.0)

    # Scatter individual points with jitter to show sample count.
    rng = np.random.default_rng(0)
    for n, vals in by_n.items():
        jx = n + rng.uniform(-0.25, 0.25, size=len(vals)) * max(1, n * 0.03)
        ax.scatter(jx, vals, s=8, color="#1f5e1f", alpha=0.45, zorder=2)

    if sat_per_n:
        xs = sorted(sat_per_n)
        ax.scatter(xs, [sat_per_n[n] for n in xs],
                   s=48, color="red", zorder=4, label="SAT-optimal c_log")
    else:
        # Fall back to overall DB minimum per N as reference, flagged
        # clearly so no one reads it as proven-optimal.
        best_per_n: dict[int, float] = {}
        for r in rows:
            if r.get("c_log") is None:
                continue
            if r["n"] not in best_per_n or r["c_log"] < best_per_n[r["n"]]:
                best_per_n[r["n"]] = r["c_log"]
        xs = sorted(best_per_n)
        ax.scatter(xs, [best_per_n[n] for n in xs],
                   s=36, color="red", marker="x",
                   label="best c_log (any source, not proven optimal)")

    ax.set_xlabel("N (vertices)")
    ax.set_ylabel(r"$c_{\log}$ of greedy / local-search runs")
    ax.set_title(
        "Plot 2 — basin width vs N  (violins: greedy sources; "
        "red: " + ("SAT-optimal" if sat_per_n else "DB best per N") + ")"
    )
    ax.grid(alpha=0.3, axis="y")
    ax.legend(loc="upper left", fontsize=9)

    out = os.path.join(ensure_img_dir(), "plot_02_basin_width.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
