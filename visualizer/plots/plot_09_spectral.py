#!/usr/bin/env python3
"""
visualizer/plots/plot_09_spectral.py
====================================
Plot 9 — spectral signature. Scatter of λ₂ / λ₁ (spectral gap ratio)
vs c_log for every cached graph. Paley and near-Ramanujan algebraic
graphs should sit at small |λ₂|/λ₁; if they also sit at small c_log a
correlation is visible.

We use the second-largest absolute adjacency eigenvalue as the
"spectral second" — for d-regular graphs this is the standard
expander measure.
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

    by_cat: dict[str, list[tuple[float, float, int]]] = {}
    dropped = 0
    for r in rows:
        eigs = r.get("eigenvalues_adj")
        lam1 = r.get("spectral_radius")
        if r.get("c_log") is None or not eigs or not lam1 or lam1 <= 0:
            dropped += 1
            continue
        # λ₂ in the graph-theory sense: max |λ| among the non-λ₁ eigenvalues.
        eigs_sorted = sorted(eigs, key=lambda x: -abs(x))
        lam2 = eigs_sorted[1] if len(eigs_sorted) > 1 else 0.0
        ratio = abs(lam2) / lam1
        by_cat.setdefault(category_for(r["source"]), []).append(
            (ratio, r["c_log"], r["n"]),
        )

    if not by_cat:
        print("[plot_09] no rows with eigenvalues cached", file=sys.stderr)
        return 1
    if dropped:
        print(f"[plot_09] dropped {dropped} rows without cached eigenvalues")

    fig, ax = plt.subplots(figsize=(10, 6), constrained_layout=True)

    for cat in ("sat", "algebraic", "circulant", "greedy", "blowup", "other"):
        if cat not in by_cat:
            continue
        color, marker, label = CATEGORY_STYLE[cat]
        pts = by_cat[cat]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.scatter(xs, ys, s=26, marker=marker,
                   facecolor=color if cat == "sat" else "none",
                   edgecolor=color, linewidth=1.0, alpha=0.8,
                   label=f"{label} ({len(pts)})")

    # Ramanujan threshold: |λ₂| ≤ 2√(d-1) ⇒ |λ₂|/λ₁ = 2√(d-1)/d. At d=8
    # (Paley N=17) this gives ≈ 0.661. We draw the envelope for a range
    # of d as a curve in λ₂/λ₁ space — but since each point is a
    # different d we just drop one faint vertical guide at the Paley
    # ratio of √(d-1)/d for d=8.
    paley_ratio = np.sqrt(7) / 8  # = 0.3307 — actual Paley-17 has λ₂ = (√17−1)/2 ≈ 1.56
    ax.axvline(paley_ratio, linestyle=":", color="#555", alpha=0.6,
               label=rf"$\sqrt{{7}}/8 \approx {paley_ratio:.2f}$  (Ramanujan-ish guide)")

    ax.set_xlabel(r"$|\lambda_2| / \lambda_1$  (spectral gap ratio)")
    ax.set_ylabel(r"$c_{\log}$")
    ax.set_title("Plot 9 — spectral signature of K4-free graphs")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)

    out = os.path.join(ensure_img_dir(), "plot_09_spectral.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
