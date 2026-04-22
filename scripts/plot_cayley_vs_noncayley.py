#!/usr/bin/env python3
"""
scripts/plot_cayley_vs_noncayley.py
===================================
Plot c_log vs N for the two frontiers:

  (a) CAYLEY-class best — sources that restrict search to Cayley graphs:
      circulant, circulant_fast, cayley, cayley_tabu,
      cyclic_exhaustive_min, dihedral_exhaustive_min,
      sat_circulant, sat_circulant_optimal.

  (b) NON-CAYLEY-class best — searches that produce arbitrary K4-free
      graphs without imposing Cayley structure: sat_exact, sat_regular,
      blowup, brown, brute_force, mattheus_verstraete, polarity,
      random, random_regular_switch, regularity, srg_catalog,
      alpha_targeted.

The gap (a) − (b) at each N tells us how much "non-Cayley headroom"
exists. If consistently near zero, Cayley is extremal and the frontier
is Cayley-determined. If substantial at specific N's (e.g., N=14, 15,
20 where sat_exact beats all Cayley), those are the N's worth attacking
with non-Cayley methods.

Writes:
  results/cayley_vs_noncayley/cayley_vs_noncayley.png
  results/cayley_vs_noncayley/cayley_vs_noncayley.csv
"""

import argparse
import csv
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

from graph_db import DB


CAYLEY_SOURCES = {
    "circulant",
    "circulant_fast",
    "cayley",
    "cayley_tabu",
    "cyclic_exhaustive_min",
    "dihedral_exhaustive_min",
    "sat_circulant",
    "sat_circulant_optimal",
}

NON_CAYLEY_SOURCES = {
    "sat_exact",
    "sat_regular",
    "blowup",
    "brown",
    "brute_force",
    "mattheus_verstraete",
    "polarity",
    "random",
    "random_regular_switch",
    "regularity",
    "srg_catalog",
    "alpha_targeted",
    "norm_graph",
}


def _best_per_n(db: DB, sources: set[str]) -> dict[int, tuple[float, str]]:
    placeholders = ",".join("?" * len(sources))
    q = (
        f"SELECT n, source, c_log FROM cache "
        f"WHERE is_k4_free = 1 AND source IN ({placeholders}) AND c_log IS NOT NULL "
        f"ORDER BY n, c_log"
    )
    rows = db.cache.raw_execute(q, tuple(sources))
    best: dict[int, tuple[float, str]] = {}
    for r in rows:
        n = int(r["n"])
        c = float(r["c_log"])
        src = r["source"]
        if n not in best or c < best[n][0]:
            best[n] = (c, src)
    return best


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-min", type=int, default=10)
    ap.add_argument("--n-max", type=int, default=100)
    ap.add_argument(
        "--outdir", default="results/cayley_vs_noncayley",
        help="output dir for png and csv"
    )
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    db = DB()
    cay = _best_per_n(db, CAYLEY_SOURCES)
    non = _best_per_n(db, NON_CAYLEY_SOURCES)

    # Align on common N's
    Ns = list(range(args.n_min, args.n_max + 1))
    cay_c = [cay.get(n, (None, None))[0] for n in Ns]
    cay_src = [cay.get(n, (None, None))[1] for n in Ns]
    non_c = [non.get(n, (None, None))[0] for n in Ns]
    non_src = [non.get(n, (None, None))[1] for n in Ns]

    # Write CSV
    csv_path = os.path.join(args.outdir, "cayley_vs_noncayley.csv")
    with open(csv_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["n", "cayley_c", "cayley_source", "noncayley_c", "noncayley_source", "gap", "winner"])
        for n, cc, csrc, nc, nsrc in zip(Ns, cay_c, cay_src, non_c, non_src):
            gap = (cc - nc) if (cc is not None and nc is not None) else None
            if cc is None and nc is None:
                winner = "none"
            elif cc is None:
                winner = "non_cayley_only"
            elif nc is None:
                winner = "cayley_only"
            elif abs(cc - nc) < 1e-4:
                winner = "tie"
            elif cc < nc:
                winner = "cayley"
            else:
                winner = "non_cayley"
            w.writerow([n, cc, csrc, nc, nsrc, gap, winner])

    # Plot
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                                   gridspec_kw={"height_ratios": [2, 1]})

    cay_Ns = [n for n, c in zip(Ns, cay_c) if c is not None]
    cay_vals = [c for c in cay_c if c is not None]
    non_Ns = [n for n, c in zip(Ns, non_c) if c is not None]
    non_vals = [c for c in non_c if c is not None]

    ax1.plot(cay_Ns, cay_vals, "o-", color="#1f77b4", label="Cayley-class best",
             markersize=4, linewidth=1.2)
    ax1.plot(non_Ns, non_vals, "s-", color="#d62728", label="Non-Cayley-class best",
             markersize=4, linewidth=1.2, alpha=0.8)
    ax1.axhline(y=0.6789, color="gray", linestyle="--", linewidth=0.6,
                label="P(17) = 0.6789")
    ax1.set_ylabel("c_log")
    ax1.set_title(f"K4-free frontier: Cayley vs Non-Cayley, N ∈ [{args.n_min}, {args.n_max}]")
    ax1.legend(loc="best")
    ax1.grid(True, alpha=0.3)

    # Gap subplot
    gap_Ns = [n for n, cc, nc in zip(Ns, cay_c, non_c) if cc is not None and nc is not None]
    gap_vals = [cc - nc for cc, nc in zip(cay_c, non_c) if cc is not None and nc is not None]
    colors = ["#2ca02c" if g < -0.01 else ("#d62728" if g > 0.01 else "#888")
              for g in gap_vals]
    ax2.bar(gap_Ns, gap_vals, color=colors, alpha=0.75)
    ax2.axhline(y=0, color="black", linewidth=0.5)
    ax2.set_ylabel("gap = c_cay − c_noncay")
    ax2.set_xlabel("N")
    ax2.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    png_path = os.path.join(args.outdir, "cayley_vs_noncayley.png")
    plt.savefig(png_path, dpi=140, bbox_inches="tight")
    plt.close()

    print(f"wrote {png_path}")
    print(f"wrote {csv_path}")

    # Summary
    n_cay_only = sum(1 for cc, nc in zip(cay_c, non_c) if cc is not None and nc is None)
    n_non_only = sum(1 for cc, nc in zip(cay_c, non_c) if cc is None and nc is not None)
    both = [(n, cc, nc) for n, cc, nc in zip(Ns, cay_c, non_c) if cc is not None and nc is not None]
    n_tie = sum(1 for _, cc, nc in both if abs(cc - nc) < 1e-4)
    n_cay_wins = sum(1 for _, cc, nc in both if cc < nc - 1e-4)
    n_non_wins = sum(1 for _, cc, nc in both if nc < cc - 1e-4)

    print()
    print("=== coverage ===")
    print(f"Cayley-only coverage (non-Cayley missing):      {n_cay_only}")
    print(f"Non-Cayley-only coverage (Cayley missing):       {n_non_only}")
    print(f"Both have a data point:                          {len(both)}")
    print()
    print("=== among N with both ===")
    print(f"Tie (|gap| < 1e-4):                              {n_tie}")
    print(f"Cayley strictly better:                          {n_cay_wins}")
    print(f"Non-Cayley strictly better:                      {n_non_wins}")
    print()
    print("=== N where non-Cayley strictly beats Cayley ===")
    for n, cc, nc in both:
        if nc < cc - 1e-4:
            src = non.get(n, (None, None))[1]
            print(f"  N={n:>3}  cayley={cc:.4f}  noncayley={nc:.4f} ({src})  Δ={cc-nc:+.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
