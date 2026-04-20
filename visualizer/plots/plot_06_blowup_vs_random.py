#!/usr/bin/env python3
"""
visualizer/plots/plot_06_blowup_vs_random.py
============================================
Plot 6 — starting-point value. At each N where we have a blow-up seed
(``blowup`` source), compare three distributions of final c_log:

    - random start + local search  (`random_regular_switch`, `random`)
    - blow-up start                (`blowup`)
    - best algebraic / circulant   (one point each, no local search)

If blow-up beats random after polish, a transformer's global pattern
extraction à la PatternBoost will add real value. If they collapse,
local search dominates and starting structure is irrelevant.
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _common import category_for, ensure_img_dir  # noqa: E402
from graph_db import open_db  # noqa: E402


def main() -> int:
    with open_db() as db:
        rows = db.query(is_k4_free=1)

    by_source: dict[str, list] = {}
    for r in rows:
        if r.get("c_log") is None:
            continue
        by_source.setdefault(r["source"], []).append(r)

    blowup_ns = sorted({r["n"] for r in by_source.get("blowup", [])})
    if not blowup_ns:
        print("[plot_06] no blowup rows in DB", file=sys.stderr)
        return 1

    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)

    width = 0.32
    xs = np.arange(len(blowup_ns))

    def _c_logs(rows_):
        return [r["c_log"] for r in rows_]

    random_dists = []
    blowup_dists = []
    algebraic_best = []
    for n in blowup_ns:
        r_rows = [r for r in rows
                  if r["n"] == n and r["source"] in ("random", "random_regular_switch")]
        b_rows = [r for r in rows if r["n"] == n and r["source"] == "blowup"]
        a_rows = [r for r in rows
                  if r["n"] == n and category_for(r["source"])
                  in ("algebraic", "circulant")]
        random_dists.append(_c_logs(r_rows))
        blowup_dists.append(_c_logs(b_rows))
        algebraic_best.append(min(_c_logs(a_rows)) if a_rows else None)

    def _box(pos, dists, color, label):
        usable = [(i, d) for i, d in enumerate(dists) if d]
        if not usable:
            return
        positions = [pos[i] for i, _ in usable]
        values = [d for _, d in usable]
        bp = ax.boxplot(
            values, positions=positions, widths=width,
            patch_artist=True, showfliers=True, zorder=2,
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(color)
            patch.set_alpha(0.45)
            patch.set_edgecolor("black")
        for med in bp["medians"]:
            med.set_color("black")
        ax.plot([], [], color=color, linewidth=6, alpha=0.45, label=label)

    _box(xs - width, random_dists, "#2ca02c", "random start + polish")
    _box(xs + 0.0,   blowup_dists, "#9467bd", "blow-up start + polish")

    # Algebraic best as red dots.
    ax.scatter(
        [xs[i] + width for i, v in enumerate(algebraic_best) if v is not None],
        [v for v in algebraic_best if v is not None],
        s=46, color="red", zorder=3, label="best algebraic / circulant",
    )

    ax.set_xticks(xs)
    ax.set_xticklabels(blowup_ns)
    ax.set_xlabel("N  (only N where blow-ups exist)")
    ax.set_ylabel(r"$c_{\log}$ after local search")
    ax.set_title("Plot 6 — blow-up vs random starting points (paired per N)")
    ax.grid(alpha=0.3, axis="y")
    ax.legend(loc="upper left", fontsize=9)

    out = os.path.join(ensure_img_dir(), "plot_06_blowup_vs_random.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
