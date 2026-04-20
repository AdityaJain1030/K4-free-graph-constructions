#!/usr/bin/env python3
"""
visualizer/plots/plot_04_codegree.py
====================================
Plot 4 — co-degree scatter. For every K4-free row with a non-null
codegree_max, plot μ_max against d²/N (pseudorandom prediction) and
against α (worst-case bound). Two panels: left = all graphs, right =
Pareto-optimal graphs only.

If the Pareto panel clusters near μ_max ≈ d²/N while the full panel is
spread, the optimiser is selecting for pseudorandomness — PatternBoost
should see that signal in the input features.
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


def _draw_panel(ax, rows, title):
    # x = d²/N, y = μ_max; colour by category
    by_cat: dict[str, list[tuple[float, float, float]]] = {}
    for r in rows:
        if r.get("codegree_max") is None or r.get("d_max") is None or not r.get("n"):
            continue
        x = r["d_max"] ** 2 / r["n"]
        y = r["codegree_max"]
        a = r.get("alpha")
        by_cat.setdefault(category_for(r["source"]), []).append((x, y, a))

    for cat in ("sat", "algebraic", "circulant", "greedy", "blowup", "other"):
        if cat not in by_cat:
            continue
        color, marker, label = CATEGORY_STYLE[cat]
        pts = by_cat[cat]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, s=22, marker=marker,
                   facecolor=color if cat == "sat" else "none",
                   edgecolor=color, linewidth=1.0, alpha=0.85,
                   label=f"{label} ({len(pts)})")

    # y = x reference (pseudorandom prediction μ_max ≈ d²/N)
    all_x = [x for v in by_cat.values() for x, _, _ in v]
    if all_x:
        hi = max(all_x)
        lo = max(min(all_x), 1e-3)
        xs = np.linspace(lo, hi, 100)
        ax.plot(xs, xs, linestyle="--", color="#d62728", alpha=0.6,
                label=r"$\mu_{\max} = d^2 / N$")

    ax.set_xlabel(r"$d_{\max}^{2} / N$  (pseudorandom prediction)")
    ax.set_ylabel(r"$\mu_{\max}$  (max co-degree)")
    ax.set_title(title)
    ax.grid(alpha=0.3, which="both")
    ax.legend(loc="upper left", fontsize=8)


def main() -> int:
    with open_db() as db:
        rows = db.query(is_k4_free=1)
    rows = [r for r in rows if r.get("codegree_max") is not None]
    if not rows:
        print("[plot_04] no rows with codegree_max; re-sync with "
              "`python scripts/db_cli.py sync --recompute`", file=sys.stderr)
        return 1

    pareto: dict[tuple[int, int], dict] = {}
    for r in rows:
        if r.get("c_log") is None:
            continue
        key = (r["n"], r["d_max"])
        if key not in pareto or r["c_log"] < pareto[key]["c_log"]:
            pareto[key] = r
    pareto_rows = list(pareto.values())

    fig, (ax_all, ax_par) = plt.subplots(
        1, 2, figsize=(14, 6), constrained_layout=True,
    )
    _draw_panel(ax_all, rows, f"all graphs ({len(rows)})")
    _draw_panel(ax_par, pareto_rows,
                f"Pareto-optimal graphs ({len(pareto_rows)})")
    fig.suptitle(r"Plot 4 — co-degree $\mu_{\max}$ vs $d^2/N$")
    out = os.path.join(ensure_img_dir(), "plot_04_codegree.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
