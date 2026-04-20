#!/usr/bin/env python3
"""
visualizer/plots/plot_01_scaling.py
===================================
Plot 1 — master scaling curve. Best known c_log per N, one point per N,
coloured by source category. Paley c_log ≈ 0.679 as a horizontal
dashed reference.

SAT-optimal / brute-force graphs are drawn as filled circles when
present. If the DB has no SAT rows the layer is skipped and logged.

Run::

    micromamba run -n k4free python visualizer/plots/plot_01_scaling.py
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
    CATEGORY_STYLE, PALEY_C_LOG, category_for, check_sat_available,
    ensure_img_dir,
)
from graph_db import open_db  # noqa: E402


def main() -> int:
    with open_db() as db:
        rows = db.query(is_k4_free=1)
    if not rows:
        print("[plot_01] no K4-free rows in graph_db", file=sys.stderr)
        return 1

    check_sat_available(rows)

    # Per-category frontier: min c_log at each N.
    by_cat_n: dict[str, dict[int, float]] = {}
    for r in rows:
        c = r.get("c_log")
        if c is None:
            continue
        cat = category_for(r["source"])
        bucket = by_cat_n.setdefault(cat, {})
        if r["n"] not in bucket or c < bucket[r["n"]]:
            bucket[r["n"]] = c

    # Overall frontier (thin grey line).
    overall: dict[int, float] = {}
    for r in rows:
        c = r.get("c_log")
        if c is None:
            continue
        if r["n"] not in overall or c < overall[r["n"]]:
            overall[r["n"]] = c

    ensure_img_dir()
    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)

    # Overall frontier as background reference.
    xs = sorted(overall)
    ax.plot(xs, [overall[n] for n in xs],
            color="#999", linewidth=1.0, alpha=0.7,
            label="best known (any source)")

    # Category layers.
    draw_order = ["sat", "algebraic", "circulant", "greedy", "blowup", "other"]
    for cat in draw_order:
        if cat not in by_cat_n:
            continue
        color, marker, label = CATEGORY_STYLE[cat]
        ns = sorted(by_cat_n[cat])
        cs = [by_cat_n[cat][n] for n in ns]
        # SAT / brute-force get filled circles as the user asked.
        filled = cat in ("sat",)
        ax.scatter(
            ns, cs, s=48, marker=marker,
            facecolor=color if filled else "none",
            edgecolor=color, linewidth=1.4,
            label=f"{label} (best per N)",
            zorder=3 if cat == "sat" else 2,
        )

    ax.axhline(PALEY_C_LOG, linestyle="--", color="#d62728", alpha=0.7,
               label=f"Paley c_log ≈ {PALEY_C_LOG:.3f}")

    # 1.0 is the triangle-free Shearer floor; K4-free is a weaker condition
    # so c_log can drop below 1.0, but 1.0 is still the obvious reference.
    ax.axhline(1.0, linestyle=":", color="black", alpha=0.35,
               label="c_log = 1 (triangle-free Shearer)")

    ax.set_xlabel("N (vertices)")
    ax.set_ylabel(r"best $c_{\log} = \alpha\, d_{\max} / (N \ln d_{\max})$")
    ax.set_title("Plot 1 — master scaling curve: best known c_log per N, by source")
    ax.set_xscale("log")
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="upper left", fontsize=9, framealpha=0.9)

    out = os.path.join(ensure_img_dir(), "plot_01_scaling.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
