#!/usr/bin/env python3
"""
visualizer/plots/plot_05_gap.py
===============================
Plot 5 — greedy ceiling vs SAT floor. Best greedy c_log per N (lower
envelope of probe-1 runs) against SAT-optimal c_log per N. Shaded
area = the gap ML needs to close.

SAT-free DB: fall back to the overall non-greedy best per N (algebraic
/ circulant / blowup frontier) and clearly flag it as "best known" not
"proven optimal".
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


def _best_per_n(rows, pred):
    best: dict[int, float] = {}
    for r in rows:
        if r.get("c_log") is None or not pred(r):
            continue
        if r["n"] not in best or r["c_log"] < best[r["n"]]:
            best[r["n"]] = r["c_log"]
    return best


def main() -> int:
    with open_db() as db:
        rows = db.query(is_k4_free=1)

    greedy_best = _best_per_n(rows, lambda r: category_for(r["source"]) == "greedy")
    has_sat = check_sat_available(rows)
    if has_sat:
        floor = _best_per_n(rows, lambda r: category_for(r["source"]) == "sat")
        floor_label = "SAT-optimal c_log"
        floor_kind = "sat"
    else:
        floor = _best_per_n(
            rows,
            lambda r: category_for(r["source"]) in ("algebraic", "circulant", "blowup"),
        )
        floor_label = "best non-greedy c_log (best known, NOT proven optimal)"
        floor_kind = "best"

    common = sorted(set(greedy_best).intersection(floor))
    if not common:
        print("[plot_05] no overlapping N between greedy and floor", file=sys.stderr)
        return 1

    x = np.array(common)
    g = np.array([greedy_best[n] for n in common])
    f = np.array([floor[n] for n in common])
    gap = g - f

    fig, (ax_top, ax_bot) = plt.subplots(
        2, 1, figsize=(10, 7), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]}, constrained_layout=True,
    )

    ax_top.fill_between(x, f, g, color="#ffbf80", alpha=0.4,
                        label="gap (greedy − floor)")
    ax_top.plot(x, g, color="#2ca02c", marker="x", linewidth=1.6,
                label="best greedy c_log (probe 1)")
    ax_top.plot(x, f, color="#1f77b4", marker="o", linewidth=1.6,
                label=floor_label)

    # Simple fit for extrapolation beyond the SAT wall: c_floor = a + b / N^γ
    if len(x) >= 4:
        try:
            from scipy.optimize import curve_fit

            def model(n, a, b, g_):
                return a + b / np.power(n, g_)
            (a, b, gm), _ = curve_fit(
                model, x, f, p0=(0.7, 5.0, 0.5),
                bounds=([0.0, -50.0, 0.0], [3.0, 50.0, 3.0]),
                maxfev=5000,
            )
            x_ext = np.linspace(x.min(), max(150, x.max() * 1.5), 200)
            ax_top.plot(x_ext, model(x_ext, a, b, gm),
                        color="#1f77b4", linestyle=":", linewidth=1.2,
                        label=f"fit  c = {a:.3f} + {b:.2f}/N^{gm:.2f}")
        except Exception as exc:
            print(f"[plot_05] curve_fit skipped: {exc}")

    ax_top.set_ylabel(r"$c_{\log}$")
    ax_top.set_title(
        "Plot 5 — greedy ceiling vs floor   (gap = room ML has to close)"
        if has_sat else
        "Plot 5 — greedy vs best-known floor   [no SAT rows; using algebraic/circulant best]"
    )
    ax_top.grid(alpha=0.3)
    ax_top.legend(loc="upper left", fontsize=9)

    ax_bot.plot(x, gap, color="#d62728", marker=".", linewidth=1.2)
    ax_bot.axhline(0, color="black", linewidth=0.6, alpha=0.6)
    ax_bot.set_xlabel("N (vertices)")
    ax_bot.set_ylabel("gap")
    ax_bot.grid(alpha=0.3)

    out = os.path.join(ensure_img_dir(), "plot_05_gap.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}  (floor kind: {floor_kind})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
