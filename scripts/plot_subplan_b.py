"""
scripts/plot_subplan_b.py
=========================
Read the CSVs produced by run_subplan_b.py and produce plots +
an asymptotic extrapolation.

Outputs (in results/subplan_b/):
  - tightness_scatter.png : L_HC / alpha vs d_max for every DB graph.
  - c_vs_n.png            : min c_log observed by N, and Paley P17 line.
  - c_vs_d.png            : observed min c_log by d_max, plus the
                            rigorous universal lower bound curve
                            c_bound_reg(d) for d-regular K4-free graphs.
  - extrapolate.png       : fit c_bound_reg(d) = A / ln(d) + B and
                            show the extrapolation out to d=50.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read_csv(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def fnum(x):
    if x is None or x == "" or x == "None":
        return None
    return float(x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", default=os.path.join(REPO, "results", "subplan_b"))
    args = ap.parse_args()

    per_graph = read_csv(os.path.join(args.in_dir, "per_graph_bounds.csv"))
    by_dmax = read_csv(os.path.join(args.in_dir, "by_dmax.csv"))
    universal_path = os.path.join(args.in_dir, "universal_by_d.csv")
    universal = read_csv(universal_path) if os.path.exists(universal_path) else []

    # ---- 1) Tightness scatter -----------------------------------------------
    xs = [int(r["d_max"]) for r in per_graph]
    ys_hc = [fnum(r["tight_HC"]) for r in per_graph]
    ys_cw = [fnum(r["tight_CW"]) for r in per_graph]
    plt.figure(figsize=(7, 5))
    plt.scatter(xs, ys_hc, s=22, alpha=0.6, label="L_HC (local hard-core)")
    plt.scatter(xs, ys_cw, s=22, alpha=0.6, label="L_CW (Caro-Wei)")
    plt.axhline(1.0, color="k", lw=0.5, ls="--")
    plt.xlabel("d_max(G)")
    plt.ylabel("bound / alpha(G)")
    plt.title("Tightness of local lower bounds vs exact alpha (DB, N<=22)")
    plt.legend()
    plt.grid(alpha=0.3)
    out = os.path.join(args.in_dir, "tightness_scatter.png")
    plt.tight_layout(); plt.savefig(out, dpi=130); plt.close()
    print("wrote", out)

    # ---- 2) min c_log observed by N -----------------------------------------
    by_n = defaultdict(list)
    for r in per_graph:
        by_n[int(r["n"])].append(fnum(r["c_log"]))
    ns = sorted(by_n)
    min_c = [min(by_n[n]) for n in ns]
    plt.figure(figsize=(7, 5))
    plt.plot(ns, min_c, "o-", label="min c_log in DB")
    plt.axhline(0.6789, color="red", lw=1.0, ls="--", label="Paley P(17) = 0.6789")
    plt.xlabel("N")
    plt.ylabel("min c_log observed")
    plt.title("Best (smallest) c_log per N from the graph database")
    plt.legend(); plt.grid(alpha=0.3)
    out = os.path.join(args.in_dir, "c_vs_n.png")
    plt.tight_layout(); plt.savefig(out, dpi=130); plt.close()
    print("wrote", out)

    # ---- 3) min c_log vs d_max; rigorous universal lower bound ---------------
    ds_obs = [int(r["d_max"]) for r in by_dmax]
    min_c_obs = [fnum(r["min_c_log_observed"]) for r in by_dmax]
    plt.figure(figsize=(7.5, 5.5))
    plt.plot(ds_obs, min_c_obs, "o-", label="min c_log in DB (empirical)")
    plt.axhline(0.6789, color="red", lw=1.0, ls="--", label="Paley P(17) = 0.6789")
    if universal:
        ds_u = np.array([int(r["d"]) for r in universal if r.get("c_bound_regular_d")])
        cs_hc = np.array([fnum(r.get("c_bound_hc") or r.get("c_bound_regular_d"))
                          for r in universal if r.get("c_bound_regular_d")])
        cs_cw = np.array([fnum(r.get("c_bound_cw") or 0.0)
                          for r in universal if r.get("c_bound_regular_d")])
        cs_best = np.array([fnum(r["c_bound_regular_d"])
                            for r in universal if r.get("c_bound_regular_d")])
        plt.plot(ds_u, cs_cw, "^--", color="purple", alpha=0.7, label="Caro-Wei: d/((d+1) ln d)")
        plt.plot(ds_u, cs_hc, "s--", color="green", alpha=0.7,
                 label="local hard-core (this script)")
        plt.plot(ds_u, cs_best, "d-", color="black", lw=2,
                 label="combined rigorous lower bound\n(d-regular K4-free)")
    plt.xlabel("d (= d_max for regular graphs)")
    plt.ylabel("c_log")
    plt.title("Empirical optima vs rigorous local lower bounds")
    plt.legend(fontsize=9); plt.grid(alpha=0.3)
    out = os.path.join(args.in_dir, "c_vs_d.png")
    plt.tight_layout(); plt.savefig(out, dpi=130); plt.close()
    print("wrote", out)

    # ---- 4) Extrapolation -----------------------------------------------------
    #
    # Theoretical asymptotic from the derivation:
    # For the worst-case T = empty graph on d vertices (which maximises
    # Z(T, lambda) = (1+lambda)^d), setting lambda* = 1/(d-1) gives
    # rho(T, lambda*) -> 1/(e(d-1)) as d -> inf.
    # So the HC bound gives c >= d * rho / ln d ~ 1/(e ln d) -> 0.
    #
    # Caro-Wei (c >= d / ((d+1) ln d)) also tends to 0 as 1/ln d.
    #
    # Fit c_bound(d) = A / ln d for d>=3 and extrapolate.
    if universal:
        rows = [r for r in universal if r.get("c_bound_regular_d")]
        ds = np.array([int(r["d"]) for r in rows], dtype=float)
        cbounds = np.array([fnum(r["c_bound_regular_d"]) for r in rows], dtype=float)
        lnd = np.log(ds)

        mask = ds >= 3
        # Two competing fits: (i) pure A/ln d (theoretical), (ii) A/ln d + B (flexible).
        A_pure = float(np.sum(cbounds[mask] * (1.0 / lnd[mask])) /
                       np.sum((1.0 / lnd[mask]) ** 2))
        X = np.column_stack([1.0 / lnd[mask], np.ones(mask.sum())])
        (A2, B2), *_ = np.linalg.lstsq(X, cbounds[mask], rcond=None)

        ds_ext = np.linspace(3, 100, 300)
        fit_pure = A_pure / np.log(ds_ext)
        fit_with_b = A2 / np.log(ds_ext) + B2

        print(f"Fit (pure A/ln d): A = {A_pure:.4f}  =>  c_bound -> 0 as d -> inf")
        print(f"  c_bound(d=20)  ~ {A_pure / math.log(20):.4f}")
        print(f"  c_bound(d=50)  ~ {A_pure / math.log(50):.4f}")
        print(f"  c_bound(d=100) ~ {A_pure / math.log(100):.4f}")
        print(f"Fit (A/ln d + B): A = {A2:.4f}, B = {B2:.4f}")

        plt.figure(figsize=(7.5, 5.5))
        plt.plot(ds, cbounds, "o", ms=7, label="rigorous bound (computed, d<=9)")
        plt.plot(ds_ext, fit_pure, "-", alpha=0.7,
                 label=f"fit  c ~ {A_pure:.3f} / ln d")
        plt.plot(ds_ext, fit_with_b, "--", alpha=0.5,
                 label=f"fit  c ~ {A2:.3f}/ln d + {B2:+.3f}")
        plt.axhline(0.6789, color="red", lw=1.0, ls="--", label="Paley P(17) = 0.6789")
        plt.axhline(0.0, color="gray", lw=0.5)
        plt.xlabel("d")
        plt.ylabel("rigorous c-lower-bound for d-regular K4-free")
        plt.title("Extrapolation: rigorous local bound decays as ~1/ln d")
        plt.legend(fontsize=9); plt.grid(alpha=0.3)
        out = os.path.join(args.in_dir, "extrapolate.png")
        plt.tight_layout(); plt.savefig(out, dpi=130); plt.close()
        print("wrote", out)

        with open(os.path.join(args.in_dir, "extrapolation_fit.txt"), "w") as f:
            f.write("Extrapolation of the rigorous universal lower bound on c\n")
            f.write("(combined Caro-Wei + local hard-core, d-regular K4-free)\n\n")
            f.write(f"Pure fit: c_bound(d) = {A_pure:.6f} / ln d\n")
            for d in (5, 10, 20, 50, 100, 1000):
                f.write(f"  d={d:<5d} => c >= {A_pure / math.log(d):.4f}\n")
            f.write("\n")
            f.write(f"Flex fit: c_bound(d) = {A2:.6f}/ln d + {B2:.6f}\n")
            f.write(f"  limit as d->inf: {B2:.6f}  (not rigorous, fit artefact)\n\n")
            f.write("Target c* (Paley P17): 0.6789\n")
            f.write("Conclusion: this local-Kovari-Wei/HC method CANNOT beat the target;\n")
            f.write("the gap to 0.6789 widens with d. See docs/theory/SUBPLAN_B.md.\n")


if __name__ == "__main__":
    main()
