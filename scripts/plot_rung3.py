"""
scripts/plot_rung3.py
=====================
Plot the Lovasz theta SDP results.
Key comparison: theta is an UPPER bound on alpha, complementing
the HC-based LOWER bounds from rungs 0 and 2.
"""

from __future__ import annotations

import csv
import math
import os
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_DIR = os.path.join(REPO, "results", "subplan_b")


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def main():
    rung3 = read_csv(os.path.join(IN_DIR, "rung3_theta.csv"))

    # 1) theta/alpha vs d_max
    xs = [int(r["d_max"]) for r in rung3]
    ys = [float(r["theta_over_alpha"]) for r in rung3]

    plt.figure(figsize=(7.5, 5))
    plt.scatter(xs, ys, s=24, alpha=0.6, color="tab:purple")
    plt.axhline(1.0, color="k", ls="--", lw=0.7, label="theta = alpha (perfect)")
    # Paley P17 highlight
    for r in rung3:
        if int(r["n"]) == 17 and int(r["d_max"]) == 8 and int(r["alpha"]) == 3:
            plt.scatter([int(r["d_max"])], [float(r["theta_over_alpha"])],
                        s=120, facecolor="none", edgecolor="red", lw=2,
                        label=f"Paley P(17): theta/alpha = sqrt(17)/3 = {math.sqrt(17)/3:.3f}")
    plt.xlabel("d_max")
    plt.ylabel("theta(G) / alpha(G)")
    plt.title("Lovasz theta vs alpha on K4-free DB graphs\n"
              "Paley P(17) shows the largest SDP gap.")
    plt.legend(fontsize=9, loc="upper left")
    plt.grid(alpha=0.3)
    out = os.path.join(IN_DIR, "rung3_theta_gap.png")
    plt.tight_layout(); plt.savefig(out, dpi=130); plt.close()
    print("wrote", out)

    # 2) c_theta vs c_log per d_max (minima)
    by_d = defaultdict(lambda: {"theta": [], "c": []})
    for r in rung3:
        d = int(r["d_max"])
        by_d[d]["theta"].append(float(r["c_theta"]))
        by_d[d]["c"].append(float(r["c_log"]))
    ds = sorted(by_d)
    min_c_theta = [min(by_d[d]["theta"]) for d in ds]
    min_c_log = [min(by_d[d]["c"]) for d in ds]

    plt.figure(figsize=(7.5, 5))
    plt.plot(ds, min_c_log, "o-", color="black", label="min c_log actual (DB)")
    plt.plot(ds, min_c_theta, "s--", color="tab:purple",
             label="min c from theta (upper bound on c in DB)")
    plt.axhline(0.6789, color="red", lw=0.8, ls="--", label="Paley P(17) = 0.6789")
    plt.xlabel("d_max")
    plt.ylabel("c_log")
    plt.title("Theta-derived c (upper bound on c per graph)\n"
              "vs actual c. Gap = SDP relaxation slack.")
    plt.legend(fontsize=9); plt.grid(alpha=0.3)
    out = os.path.join(IN_DIR, "rung3_c_vs_d.png")
    plt.tight_layout(); plt.savefig(out, dpi=130); plt.close()
    print("wrote", out)

    # 3) master comparison plot: rung 0 LB, rung 2 LB, rung 3 UB, actual
    by_d_r2 = read_csv(os.path.join(IN_DIR, "rung2_by_dmax.csv"))
    by_d_r0 = read_csv(os.path.join(IN_DIR, "by_dmax.csv"))
    universal = read_csv(os.path.join(IN_DIR, "universal_by_d.csv"))

    ds_r2 = [int(r["d_max"]) for r in by_d_r2]
    minc_r2 = [float(r["min_c_bound_rung2"]) for r in by_d_r2]
    minobs  = [float(r["min_c_log_obs"]) for r in by_d_r2]

    ds_univ = [int(r["d"]) for r in universal if r.get("c_bound_regular_d")]
    univ    = [float(r["c_bound_regular_d"]) for r in universal if r.get("c_bound_regular_d")]

    plt.figure(figsize=(8.5, 6))
    # Rigorous LB: universal rung 0
    plt.plot(ds_univ, univ, "d-", color="tab:orange",
             label="rung 0 (universal LB, rigorous for d-reg K4-free)")
    # Empirical LB from rung 2
    plt.plot(ds_r2, minc_r2, "s--", color="tab:green",
             label="rung 2 (exact HC LB in DB, not universal)")
    # Actual
    plt.plot(ds_r2, minobs, "o-", color="black", label="actual min c_log (DB)")
    # UB from theta
    plt.plot(ds, min_c_theta, "^--", color="tab:purple",
             label="rung 3 (theta upper bound on c in DB)")
    plt.axhline(0.6789, color="red", lw=0.8, ls="--",
                label="target: Paley P(17) = 0.6789")
    plt.xlabel("d_max")
    plt.ylabel("c_log")
    plt.title("Full picture: LB methods (rung 0, 2), actual, UB method (rung 3)")
    plt.legend(fontsize=9, loc="upper right")
    plt.grid(alpha=0.3)
    out = os.path.join(IN_DIR, "rung_all_compare.png")
    plt.tight_layout(); plt.savefig(out, dpi=130); plt.close()
    print("wrote", out)


if __name__ == "__main__":
    main()
