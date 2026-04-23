"""
Summarise results/all_k4free_theta.csv: how tight is Lovász θ
across the entire K4-free DB?

Tightness has two sides:
  (1) θ vs α   — how much SDP slack remains above the actual α
  (2) θ vs H   — how much Hoffman is loose relative to θ
"""
import csv
import os
from collections import defaultdict
from statistics import median

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(os.path.dirname(HERE), "results", "all_k4free_theta.csv")


def main():
    rows = []
    with open(CSV) as f:
        for r in csv.DictReader(f):
            r["n"] = int(r["n"])
            r["alpha"] = int(r["alpha"])
            for k in ("d", "lam_min", "hoffman", "theta", "theta_over_alpha",
                     "alpha_over_theta", "theta_over_hoff", "alpha_over_hoff",
                     "c_log"):
                r[k] = float(r[k]) if r[k] not in ("", None) else None
            rows.append(r)
    N = len(rows)
    print(f"Total unique K4-free graphs with θ: {N}\n")

    def frac(cond):
        c = sum(1 for r in rows if cond(r))
        return c, 100 * c / N

    # (1) θ tightness on α
    print("=== θ tightness on α  (how close is SDP ceiling to true α?) ===")
    c, p = frac(lambda r: abs(r["theta"] - r["alpha"]) < 1e-2)
    print(f"  α = θ (within 1e-2):         {c:4d}  ({p:5.1f}%)  SDP proves α exact")
    c, p = frac(lambda r: r["theta"] - r["alpha"] < 1 and r["theta"] - r["alpha"] >= 1e-2)
    print(f"  θ − α < 1:                   {c:4d}  ({p:5.1f}%)  integer α would match")
    c, p = frac(lambda r: 1 <= r["theta"] - r["alpha"] < 3)
    print(f"  1 ≤ θ − α < 3:               {c:4d}  ({p:5.1f}%)")
    c, p = frac(lambda r: 3 <= r["theta"] - r["alpha"] < 6)
    print(f"  3 ≤ θ − α < 6:               {c:4d}  ({p:5.1f}%)")
    c, p = frac(lambda r: r["theta"] - r["alpha"] >= 6)
    print(f"  θ − α ≥ 6:                   {c:4d}  ({p:5.1f}%)")

    ratios = [r["theta_over_alpha"] for r in rows]
    print(f"\n  θ/α   min={min(ratios):.3f}  median={median(ratios):.3f} "
          f"mean={sum(ratios)/len(ratios):.3f}  max={max(ratios):.3f}")
    rel_gap = [(r["theta"] - r["alpha"]) / r["alpha"] for r in rows]
    print(f"  (θ-α)/α  median={median(rel_gap):.3f}  "
          f"mean={sum(rel_gap)/len(rel_gap):.3f}  max={max(rel_gap):.3f}")

    # (2) θ vs Hoffman
    print("\n=== θ vs Hoffman (SDP ceiling tighter than spectral?) ===")
    reg = [r for r in rows if r["theta_over_hoff"] is not None]
    c = sum(1 for r in reg if abs(r["theta"] - r["hoffman"]) < 1e-3)
    print(f"  θ = H  (to 1e-3):            {c:4d}  ({100*c/len(reg):5.1f}% of {len(reg)} regular)")
    c = sum(1 for r in reg if r["theta"] < r["hoffman"] - 1e-3)
    print(f"  θ < H  strictly:             {c:4d}  ({100*c/len(reg):5.1f}%)")

    ratios = [r["theta_over_hoff"] for r in reg]
    print(f"\n  θ/H   min={min(ratios):.3f}  median={median(ratios):.3f} "
          f"mean={sum(ratios)/len(ratios):.3f}  max={max(ratios):.3f}")
    ratios = [r["alpha_over_hoff"] for r in reg]
    print(f"  α/H   min={min(ratios):.3f}  median={median(ratios):.3f} "
          f"mean={sum(ratios)/len(ratios):.3f}  max={max(ratios):.3f}")
    ratios = [r["alpha_over_theta"] for r in rows]
    print(f"  α/θ   min={min(ratios):.3f}  median={median(ratios):.3f} "
          f"mean={sum(ratios)/len(ratios):.3f}  max={max(ratios):.3f}")

    # Per-source breakdown
    print("\n=== Per-source tightness ===")
    print(f"{'source':28s} {'n':>4s} {'α=θ%':>6s} {'θ=H%':>6s} "
          f"{'θ/ᾱ':>6s} {'α/H̄':>6s}")
    by_src = defaultdict(list)
    for r in rows:
        by_src[r["source"]].append(r)
    for src in sorted(by_src, key=lambda s: -len(by_src[s])):
        rs = by_src[src]
        eq_theta = sum(1 for r in rs if abs(r["theta"] - r["alpha"]) < 1e-2)
        reg_rs = [r for r in rs if r["theta_over_hoff"] is not None]
        eq_h = sum(1 for r in reg_rs if abs(r["theta"] - r["hoffman"]) < 1e-3) if reg_rs else 0
        mean_ta = sum(r["theta_over_alpha"] for r in rs) / len(rs)
        mean_ah = (sum(r["alpha_over_hoff"] for r in reg_rs) / len(reg_rs)) if reg_rs else 0
        print(f"{src:28s} {len(rs):4d} "
              f"{100*eq_theta/len(rs):5.1f}% "
              f"{(100*eq_h/len(reg_rs) if reg_rs else 0):5.1f}% "
              f"{mean_ta:6.3f} {mean_ah:6.3f}")

    # (3) α/θ at small n (where α-exact can be verified visually)
    print("\n=== Tightness by n (α-exact where θ integer-equals α) ===")
    print(f"{'n':>4s}  {'N':>4s}  {'α=θ':>5s}  {'θ=H':>5s}  {'θ/ᾱ':>6s} {'α/H̄':>6s}")
    by_n = defaultdict(list)
    for r in rows:
        by_n[r["n"]].append(r)
    for n in sorted(by_n):
        rs = by_n[n]
        eq_theta = sum(1 for r in rs if abs(r["theta"] - r["alpha"]) < 1e-2)
        reg_rs = [r for r in rs if r["theta_over_hoff"] is not None]
        eq_h = sum(1 for r in reg_rs if abs(r["theta"] - r["hoffman"]) < 1e-3) if reg_rs else 0
        mean_ta = sum(r["theta_over_alpha"] for r in rs) / len(rs)
        mean_ah = (sum(r["alpha_over_hoff"] for r in reg_rs) / len(reg_rs)) if reg_rs else 0
        if n % 5 == 0 or n in (17, 19, 23, 29, 37, 41, 43, 47, 53):
            print(f"{n:>4d}  {len(rs):4d}  {eq_theta:5d}  {eq_h:5d}  "
                  f"{mean_ta:6.3f} {mean_ah:6.3f}")

    # (4) largest SDP slack (θ - α)
    print("\n=== Top 12 largest θ − α (SDP ceiling far above α) ===")
    print(f"  n   α     θ        H     θ−α   src")
    for r in sorted(rows, key=lambda x: -(x["theta"] - x["alpha"]))[:12]:
        print(f"  {r['n']:3d}  {r['alpha']:3d}  {r['theta']:7.3f} "
              f"{r['hoffman']:7.3f}  {r['theta']-r['alpha']:5.2f}  "
              f"{r['source']}")

    # (5) smallest θ − α (tight)
    print("\n=== Certified α-exact (θ = α) — best extremal witnesses ===")
    exact = [r for r in rows if abs(r["theta"] - r["alpha"]) < 1e-2]
    print(f"Total: {len(exact)} graphs with α = θ (SDP tight)")
    # print range of c_log among them
    if exact:
        cls = [r["c_log"] for r in exact if r["c_log"] is not None]
        cls.sort()
        print(f"  c_log range: {cls[0]:.4f} to {cls[-1]:.4f} (median {median(cls):.4f})")
        by_n_exact = defaultdict(int)
        for r in exact:
            by_n_exact[r["n"]] += 1
        print(f"  n distribution (top 10):", sorted(by_n_exact.items())[:10])


if __name__ == "__main__":
    main()
