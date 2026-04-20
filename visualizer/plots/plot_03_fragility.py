#!/usr/bin/env python3
"""
visualizer/plots/plot_03_fragility.py
=====================================
Plot 3 — fragility curves, normalised. Reads
``visualizer/plots/data/fragility.json`` and plots
(Δ c_log / c_log(0)) vs step for every N. Inset: the step-1 slope
(fragility index) vs N — steep at small N, shallow at large N ⇒
landscape smoothing.

This is a re-render of the raw trajectories in plot_fragility.py using
the definition the user asked for in Probe 2.
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from _common import ensure_img_dir  # noqa: E402

IN_JSON = os.path.join(HERE, "data", "fragility.json")


def main() -> int:
    if not os.path.exists(IN_JSON):
        print(f"[plot_03] no {IN_JSON}; run scripts/run_fragility.py first",
              file=sys.stderr)
        return 1

    with open(IN_JSON) as f:
        data = json.load(f)
    results = sorted(data["results"], key=lambda r: r["n"])
    steps = data["record_steps"]
    if not results:
        print("[plot_03] empty fragility.json", file=sys.stderr)
        return 1

    ns = [r["n"] for r in results]
    norm = matplotlib.colors.Normalize(vmin=min(ns), vmax=max(ns))
    cmap = plt.get_cmap("viridis")

    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)

    step_arr = np.array(steps, dtype=float)
    mask = step_arr > 0

    step1_slope = []  # (N, Δ/c_0 at step 1)

    for r in results:
        mean = np.array(r["mean_c_log"], dtype=float)
        c0 = mean[0]
        if not (c0 and np.isfinite(c0) and c0 > 0):
            continue
        frac = (mean - c0) / c0
        color = cmap(norm(r["n"]))
        ax.plot(step_arr[mask], frac[mask],
                color=color, linewidth=1.1, alpha=0.75)

        # step-1 slope = fractional change after one step
        if steps[0] == 0 and len(steps) > 1 and steps[1] == 1:
            step1_slope.append((r["n"], frac[1]))

    ax.set_xscale("log")
    ax.set_xlabel("walk step (log)")
    ax.set_ylabel(r"$\Delta c_{\log} / c_{\log}(0)$  (fractional degradation)")
    ax.axhline(0, color="black", linewidth=0.7, alpha=0.6)
    ax.grid(alpha=0.3, which="both")
    ax.set_title(
        f"Plot 3 — fragility curves  "
        f"({len(results)} seeds, trials={data['trials']}, "
        f"walk={data['walk_length']}, α={data['alpha_solver']})"
    )

    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02, aspect=40)
    cbar.set_label("N (starting graph size)")

    # Inset: step-1 slope vs N.
    if step1_slope:
        from mpl_toolkits.axes_grid1.inset_locator import inset_axes
        inset = inset_axes(
            ax, width="38%", height="30%",
            loc="lower right", borderpad=1.2,
        )
        ns_ins = [p[0] for p in step1_slope]
        slopes = [p[1] for p in step1_slope]
        inset.scatter(ns_ins, slopes, s=12, color="#1f77b4", alpha=0.85)
        inset.set_xlabel("N", fontsize=8)
        inset.set_ylabel(r"step-1 $\Delta c_{\log} / c_0$", fontsize=8)
        inset.set_title("fragility index", fontsize=9)
        inset.tick_params(labelsize=7)
        inset.grid(alpha=0.3)
        inset.axhline(0, color="black", linewidth=0.6, alpha=0.5)

    out = os.path.join(ensure_img_dir(), "plot_03_fragility.png")
    fig.savefig(out, dpi=160, bbox_inches="tight")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
